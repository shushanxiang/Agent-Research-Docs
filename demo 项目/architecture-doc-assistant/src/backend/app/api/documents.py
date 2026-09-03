"""
文档管理路由
============
POST   /upload          — 上传文档，解析后追加到共享检索索引
GET    /                — 文档列表
GET    /{id}            — 文档详情
"""

import hashlib
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, HTTPException

from app.core.deps import get_current_user
from app.core.registry import add_document_chunks, get_stats, reset_index
from app.services.parse import ParseService

logger = logging.getLogger(__name__)

router = APIRouter()
_parse_service = ParseService()

# ── 文件存储目录 ──
# Docker: /app/uploads (映射 data/uploads)
# Docker: /app/markdown (映射 data/markdown)
# 本地: src/data/uploads  /  src/data/markdown
_UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "data/uploads"))
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
_MARKDOWN_DIR = Path(os.getenv("MARKDOWN_DIR", "data/markdown"))
_MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)

# 简易内存存储（生产替换 PostgreSQL）
_documents: dict = {}


def _raw_text_to_chunks(raw_text: str, doc_id: str, metadata: dict) -> list:
    """
    将解析后的纯文本拆分 chunk 并标记元数据。

    策略:
      1. 如果有明确的条款编号模式（如 "4.1.3"），按条款切
      2. 否则按段落切，每个段落一个 chunk
    """
    chunks = []
    standard_code = metadata.get("standard_code", "")
    title = metadata.get("standard_code", "") or metadata.get("title", "")

    # 尝试按条款编号拆分
    clause_pattern = re.compile(r"(?:(?:第?\s*)?(\d+\.\d+\.\d+)\s*(?:条\s*)?)")
    parts = clause_pattern.split(raw_text)

    if len(parts) > 2:
        # 有条款编号：第 0 号是前言，之后 (id, content) 成对
        for i in range(1, len(parts), 2):
            clause_id = parts[i]
            content = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if content:
                chunks.append({
                    "chunk_id": str(uuid.uuid4())[:8],
                    "content": f"{clause_id} {content}"[:500],
                    "metadata": {
                        "chapter": "",
                        "clause_id": clause_id,
                        "standard_code": standard_code,
                        "standard_title": title,
                        "status": metadata.get("status", "有效"),
                        "page_num": 1,
                    },
                })
    else:
        # 无条款编号：按段落切
        paragraphs = [p.strip() for p in raw_text.split("\n") if p.strip()]
        for idx, para in enumerate(paragraphs[:50]):  # 最多 50 段
            # 尝试从段落中提取条目编号
            code_match = re.search(r"(\d+\.\d+\.\d+)", para)
            clause_id = code_match.group(1) if code_match else f"P{idx+1}"

            chunks.append({
                "chunk_id": str(uuid.uuid4())[:8],
                "content": para[:500],
                "metadata": {
                    "chapter": "",
                    "clause_id": clause_id,
                    "standard_code": standard_code,
                    "standard_title": title,
                    "status": metadata.get("status", "有效"),
                    "page_num": 1,
                },
            })

    # 如果没有任何 chunk，至少保留一个
    if not chunks and raw_text.strip():
        chunks.append({
            "chunk_id": str(uuid.uuid4())[:8],
            "content": raw_text[:500],
            "metadata": {
                "chapter": "",
                "clause_id": "全文",
                "standard_code": standard_code,
                "standard_title": title,
                "status": metadata.get("status", "有效"),
                "page_num": 1,
            },
        })

    return chunks


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    project_id: str | None = Form(None),
    category: str | None = Form(None),
    description: str | None = Form(None),
    version_strategy: str = Form("auto_increment"),
    user: dict = Depends(get_current_user),
):
    """上传文档，解析后追加到共享检索索引"""
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()[:16]

    # 写入磁盘
    safe_name = re.sub(r"[^\w.\-]", "_", file.filename)
    storage_path = _UPLOAD_DIR / f"{file_hash}_{safe_name}"
    storage_path.write_bytes(content)

    # 解析文档
    parse_result = _parse_service.parse_text_from_bytes(content, file.filename)
    raw_text = parse_result.get("raw_text", "")
    parser_name = parse_result.get("parser", "unknown")
    metadata = _parse_service.extract_metadata(raw_text, doc_type_hint=category)

    # ── 保存 Markdown 解析结果 ──
    md_filename = file_hash + ".md"
    md_path = _MARKDOWN_DIR / md_filename
    md_path.write_text(raw_text, encoding="utf-8")
    markdown_url = f"/markdown/{md_filename}"
    logger.info(
        "[Documents] Markdown 已保存: %s (%d chars)",
        md_path, len(raw_text),
    )

    # 存储文档
    doc_id = file_hash
    _documents[doc_id] = {
        "id": doc_id,
        "filename": file.filename,
        "storage_path": str(storage_path),
        "category": category or metadata.get("doc_type", "规范"),
        "file_size": len(content),
        "hash": file_hash,
        "status": "completed",
        "metadata": metadata,
        "raw_text": raw_text[:2000],
        "full_markdown": raw_text,      # 完整 Markdown 内容
        "markdown_path": str(md_path),   # 磁盘路径
        "markdown_url": markdown_url,    # HTTP 访问 URL
        "parser": parser_name,
        "uploaded_at": datetime.now().isoformat(),
        "uploader": user["user_id"],
    }

    # 文本分块 → 追加到共享检索索引

    # 拒绝无效解析结果（PDF 二进制误解码 或 无法解析）
    if parser_name == "rejected":
        logger.warning(
            "[Documents] 文档 %s 解析被拒绝 (parser=%s)，不加入检索索引",
            file.filename, parser_name,
        )
        chunk_count = 0
    else:
        chunks = _raw_text_to_chunks(raw_text, doc_id, metadata)
        chunk_count = len(chunks)
        add_document_chunks(chunks, doc_id, file.filename)
        logger.info(
            "[Documents] 文档 %s 已索引: %d chunks (parser=%s)",
            file.filename, chunk_count, parser_name,
        )

    return {
        "document_id": doc_id,
        "filename": file.filename,
        "storage_path": str(storage_path),
        "markdown_path": str(md_path),
        "markdown_url": markdown_url,
        "category": _documents[doc_id]["category"],
        "status": "completed",
        "parser": parser_name,
        "metadata": metadata,
        "chunks_indexed": chunk_count,
        "total_chunks": get_stats()["total_chunks"],
        "created_at": datetime.now().isoformat(),
    }


@router.get("/")
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str | None = None,
    status: str | None = None,
    user: dict = Depends(get_current_user),
):
    """文档列表（分页+筛选）"""
    items = list(_documents.values())
    if category:
        items = [d for d in items if d.get("category") == category]
    total = len(items)
    start = (page - 1) * page_size
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items[start:start + page_size],
    }


@router.get("/stats")
async def index_stats():
    """查看当前索引状态"""
    from app.core.registry import get_stats as _stats
    return _stats()


@router.post("/reset")
async def reset_index_endpoint():
    """清空搜索索引（调试用）"""
    reset_index()
    _documents.clear()
    return {"message": "索引已重置", "stats": get_stats()}


@router.get("/{document_id}")
async def get_document(document_id: str, user: dict = Depends(get_current_user)):
    """文档详情"""
    doc = _documents.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc
