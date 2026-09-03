"""
ChromaDB 向量数据库模块
=======================
Chroma 客户端封装，管理 Collection 和向量索引。

Collection 设计：
- regulations:  规范条款向量 (1024d dense  + metadata)
- atlas_nodes:  图集节点向量 (1024d dense  + metadata)
- images:       图集图片向量 (1024d dense  + metadata)

替代原 core/registry.py 中的 _all_chunks 内存列表。
"""

import logging
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings as app_settings
from app.services.embedding import (
    embed_documents,
    embed_query,
    is_embedding_available,
    get_embedding_mode,
)

logger = logging.getLogger(__name__)

# chromadb 延迟导入
chromadb = None

# ── Collection 常量 ──
COLLECTION_REGULATIONS = "regulations"
COLLECTION_ATLAS_NODES = "atlas_nodes"
COLLECTION_IMAGES = "images"

# ── Chroma 客户端（延迟初始化）──
_chroma_client = None  # Optional[chromadb.ClientAPI]
_chroma_available = False
_chroma_mode = "unavailable"  # "http" | "embedded" | "unavailable"
# 嵌入式持久化目录（无 Docker 时自动落盘）
_EMBEDDED_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "chroma")


def _get_chroma_client():
    """
    延迟初始化 Chroma 客户端。

    优先模式：
      1. HTTP 模式 — 连接 Docker 容器 (CHROMA_HOST:CHROMA_PORT)
      2. 嵌入式模式 — 本地 PersistentClient，向量落盘 data/chroma/

    两种都不可用时返回 None，检索降级为内存关键词匹配。
    """
    global _chroma_client, _chroma_available, _chroma_mode, chromadb

    if _chroma_client is not None:
        return _chroma_client

    try:
        import chromadb as _chromadb_mod
        chromadb = _chromadb_mod
        from chromadb.config import Settings as ChromaSettings
    except ImportError as e:
        logger.warning(f"[ChromaDB] chromadb 未安装: {e}")
        return None

    # ── 模式 1: HTTP 连接 ──
    try:
        _chroma_client = chromadb.HttpClient(
            host=app_settings.CHROMA_HOST,
            port=app_settings.CHROMA_PORT,
            settings=ChromaSettings(
                anonymized_telemetry=False,
            ),
        )
        _chroma_client.heartbeat()
        _chroma_available = True
        _chroma_mode = "http"
        logger.info(
            f"[ChromaDB] HTTP 模式: {app_settings.CHROMA_HOST}:{app_settings.CHROMA_PORT}"
        )
        return _chroma_client
    except Exception as e:
        logger.warning(
            f"[ChromaDB] HTTP 连接失败 ({e})，尝试嵌入式持久化模式"
        )
        _chroma_client = None

    # ── 模式 2: 嵌入式持久化 ──
    try:
        os.makedirs(_EMBEDDED_DIR, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(
            path=_EMBEDDED_DIR,
            settings=ChromaSettings(
                anonymized_telemetry=False,
            ),
        )
        _chroma_available = True
        _chroma_mode = "embedded"
        logger.info(f"[ChromaDB] 嵌入式模式: 向量持久化至 {_EMBEDDED_DIR}")
        return _chroma_client
    except Exception as e2:
        logger.warning(f"[ChromaDB] 嵌入式模式失败 ({e2})，降级为内存关键词匹配")
        _chroma_client = None
        _chroma_available = False
        _chroma_mode = "unavailable"

    return _chroma_client


def is_chroma_available() -> bool:
    _get_chroma_client()
    return _chroma_available


def get_chroma_mode() -> str:
    """获取当前 Chroma 模式: http / embedded / unavailable"""
    _get_chroma_client()
    return _chroma_mode


# ── Collection 管理 ──


def get_or_create_collection(
    name: str,
    embedding_function=None,  # 不使用 Chroma 内置 embedding，自行控制
) -> Optional[Any]:
    """
    获取或创建 Chroma Collection。

    统一使用 cosine 距离度量，与 BGE-M3 L2 归一化后的 dot product 等效。
    """
    client = _get_chroma_client()
    if not client:
        return None

    try:
        collection = client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=embedding_function,
        )
        return collection
    except Exception as e:
        logger.error(f"[ChromaDB] 创建 Collection '{name}' 失败: {e}")
        return None


def _get_regulations_collection():
    return get_or_create_collection(COLLECTION_REGULATIONS)


def _get_atlas_collection():
    return get_or_create_collection(COLLECTION_ATLAS_NODES)


def _get_images_collection():
    return get_or_create_collection(COLLECTION_IMAGES)


# ── 文档索引 ──


def index_document_chunks(
    chunks: List[Dict],
    collection_name: str = COLLECTION_REGULATIONS,
) -> int:
    """
    将文档 chunk 批量写入 Chroma 向量库。

    Args:
        chunks: [{chunk_id, content, metadata}, ...]
        collection_name: 目标 Collection

    Returns:
        成功写入的 chunk 数量

    当 Chroma 或 Embedding 不可用时返回 0。
    """
    if not chunks:
        return 0

    collection = get_or_create_collection(collection_name)
    if not collection:
        logger.warning(f"[ChromaDB] 索引跳过: Collection '{collection_name}' 不可用")
        return 0

    # 生成 Embedding
    texts = [c.get("content", "") for c in chunks]
    if is_embedding_available():
        embeddings = embed_documents(texts)
    else:
        logger.warning("[ChromaDB] 索引跳过: Embedding 不可用")
        return 0

    # 准备写入数据
    ids = [c.get("chunk_id", str(uuid.uuid4())[:8]) for c in chunks]
    metadatas = []
    for c in chunks:
        meta = c.get("metadata", {})
        # Chroma 只接受 str/int/float/bool 值
        clean_meta = {
            k: str(v) if not isinstance(v, (str, int, float, bool)) else v
            for k, v in meta.items()
        }
        metadatas.append(clean_meta)

    try:
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        logger.info(
            f"[ChromaDB] 索引完成: {len(chunks)} chunks → '{collection_name}' "
            f"(embedding={get_embedding_mode()})"
        )
    except Exception as e:
        logger.error(f"[ChromaDB] 写入失败: {e}")
        return 0

    return len(chunks)


# ── 向量检索 ──


def search_by_vector(
    query: str,
    collection_name: str = COLLECTION_REGULATIONS,
    top_k: int = 10,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Tuple[float, Dict]]:
    """
    向量语义检索。

    Args:
        query: 查询文本
        collection_name: 目标 Collection
        top_k: 返回数量
        filters: Chroma where 过滤条件

    Returns:
        [(score, {content, metadata}), ...] 按相似度降序
    """
    collection = get_or_create_collection(collection_name)
    if not collection:
        return []

    query_vec = embed_query(query)

    try:
        results = collection.query(
            query_embeddings=[query_vec],
            n_results=top_k,
            where=filters,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        logger.error(f"[ChromaDB] 检索失败: {e}")
        return []

    if not results or not results["ids"] or not results["ids"][0]:
        return []

    scored = []
    for i in range(len(results["ids"][0])):
        # cosine distance → similarity score
        distance = results["distances"][0][i] if results.get("distances") else 0.0
        similarity = 1.0 - distance

        scored.append((
            similarity,
            {
                "chunk_id": results["ids"][0][i],
                "content": results["documents"][0][i]
                if results.get("documents")
                else "",
                "metadata": results["metadatas"][0][i]
                if results.get("metadatas")
                else {},
            },
        ))

    return scored


def search_by_text(
    query: str,
    collection_name: str = COLLECTION_REGULATIONS,
    top_k: int = 10,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Tuple[float, Dict]]:
    """
    关键词全文检索（本地字符重叠打分，模拟 BM25 稀疏检索）。

    说明：不使用 Chroma 的 query_texts，因为那会触发内置 ONNX 模型的下载。
    本项目的 Embedding 由 BGE-M3 / DashScope 统一管理，因此关键词检索
    改为从 Collection 拉取内容后做字符重叠度打分，补充稠密检索。
    """
    collection = get_or_create_collection(collection_name)
    if not collection:
        return []

    query_chars = set(query.replace("？", "").replace("?", "").strip())
    if not query_chars:
        return []

    try:
        data = collection.get(include=["documents", "metadatas"])
    except Exception as e:
        logger.warning(f"[ChromaDB] 获取 Collection 数据失败: {e}")
        return []

    ids = data.get("ids", [])
    documents = data.get("documents", [])
    metadatas = data.get("metadatas", [])

    scored = []
    for i in range(len(ids)):
        meta = metadatas[i] if i < len(metadatas) else {}
        if filters and not _match_filters(meta, filters):
            continue

        content = documents[i] if i < len(documents) else ""
        hit_chars = sum(1 for ch in query_chars if ch in content)
        score = hit_chars / max(len(query_chars), 1)

        # 条款号精确匹配加分
        clause_id = meta.get("clause_id", "")
        if clause_id and clause_id in query:
            score += 1.0

        scored.append((
            score,
            {
                "chunk_id": ids[i],
                "content": content,
                "metadata": meta,
            },
        ))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]


def _match_filters(meta: Dict, filters: Dict) -> bool:
    """检查 chunk 元数据是否满足过滤条件"""
    for key, value in filters.items():
        if key == "status":
            allowed = value if isinstance(value, list) else [value]
            if meta.get("status") not in allowed:
                return False
        elif key == "standard_code":
            if value not in meta.get("standard_code", ""):
                return False
        elif meta.get(key) != value:
            return False
    return True


# ── Collection 管理 ──


def count_collection(collection_name: str) -> int:
    """获取 Collection 中数据条数"""
    collection = get_or_create_collection(collection_name)
    if not collection:
        return 0
    return collection.count()


def reset_collection(collection_name: str):
    """清空 Collection（调试用，生产环境需鉴权）"""
    client = _get_chroma_client()
    if client:
        try:
            client.delete_collection(collection_name)
            logger.info(f"[ChromaDB] Collection '{collection_name}' 已删除")
        except Exception:
            pass
        # 重新创建
        get_or_create_collection(collection_name)


def reset_all_collections():
    """清空所有 Collection"""
    for name in [COLLECTION_REGULATIONS, COLLECTION_ATLAS_NODES, COLLECTION_IMAGES]:
        reset_collection(name)
    logger.info("[ChromaDB] 所有 Collection 已重置")


def get_stats() -> dict:
    """获取 ChromaDB 状态"""
    return {
        "chroma_available": _chroma_available,
        "chroma_mode": get_chroma_mode(),
        "embedding_mode": get_embedding_mode() if is_embedding_available() else "unavailable",
        "collections": {
            COLLECTION_REGULATIONS: count_collection(COLLECTION_REGULATIONS),
            COLLECTION_ATLAS_NODES: count_collection(COLLECTION_ATLAS_NODES),
            COLLECTION_IMAGES: count_collection(COLLECTION_IMAGES),
        },
    }
