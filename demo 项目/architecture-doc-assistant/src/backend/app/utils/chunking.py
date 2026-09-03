"""
文本切块工具
============
将解析后的结构化条款拆分为适合 RAG 检索的 chunk。
"""

import logging
import uuid
from typing import Dict, List

logger = logging.getLogger(__name__)


def chunk_clauses(parsed_document: dict) -> List[Dict]:
    """
    将解析后的章节/条款拆分为独立 chunk。

    每个 chunk 包含完整的条款内容 + 元数据（章节路径、规范编号、状态等）。

    Args:
        parsed_document: MinerU 解析后的结构化文档
            {
                "metadata": { "standard_code": "...", "title": "...", "status": "..." },
                "chapters": [
                    {
                        "title": "总则",
                        "clauses": [
                            { "clause_id": "1.0.1", "content": "...", "page_num": 1 }
                        ]
                    }
                ]
            }

    Returns:
        List[dict]: 每个元素包含 chunk_id, content, metadata
    """
    meta = parsed_document.get("metadata", {})
    chunks = []

    for chapter in parsed_document.get("chapters", []):
        chapter_title = chapter.get("title", "")
        for clause in chapter.get("clauses", []):
            chunk = {
                "chunk_id": str(uuid.uuid4())[:8],
                "content": clause.get("content", ""),
                "metadata": {
                    "chapter": chapter_title,
                    "clause_id": clause.get("clause_id", ""),
                    "standard_code": meta.get("standard_code", ""),
                    "standard_title": meta.get("title", ""),
                    "status": meta.get("status", "有效"),
                    "page_num": clause.get("page_num", 1),
                },
            }
            chunks.append(chunk)

    logger.info(f"Chunked {len(chunks)} clauses from {len(parsed_document.get('chapters', []))} chapters")
    return chunks
