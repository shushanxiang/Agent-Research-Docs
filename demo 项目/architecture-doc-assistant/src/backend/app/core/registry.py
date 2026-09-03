"""
共享数据注册中心 (Singleton) v2.0
================================
统一管理 ChromaDB、PostgreSQL、Embedding、MinIO 四大模块的初始化与访问。

核心职责：
  - 文档 chunks → ChromaDB 向量库（稠密检索）
  - 文档元数据   → PostgreSQL（持久化 CRUD）
  - 文件存储     → MinIO（或本地降级）
  - Embedding   → BGE-M3（或 DashScope 降级）
  - 检索服务     → HybridRetrieverV2（Chroma 多路检索 + RRF + Rerank）
  - 问答服务     → RegulationQAService / AtlasQAService

向后兼容：
  - ChromaDB 不可用时降级为内存关键词检索
  - PostgreSQL 不可用时降级为内存字典
  - MinIO 不可用时降级为本地文件系统
  - BGE-M3 不可用时降级为 DashScope / 零向量
"""

import logging
from typing import Dict, List, Optional

from app.core.config import settings
from app.core.vectordb import (
    index_document_chunks,
    search_by_vector,
    reset_all_collections as reset_chroma,
    get_stats as get_chroma_stats,
    is_chroma_available,
    COLLECTION_REGULATIONS,
    COLLECTION_ATLAS_NODES,
)
from app.services.embedding import is_embedding_available, get_embedding_mode
from app.services.storage import is_minio_available
from app.services.search import SearchService
from app.services.chat import RegulationQAService, AtlasQAService
from app.retrievers.hybrid import HybridRetriever
from app.retrievers.hybrid_dense import HybridRetrieverV2

logger = logging.getLogger(__name__)

# ── 全局状态 ──
_search_service = SearchService()
_regulation_qa: Optional[RegulationQAService] = None
_atlas_qa = AtlasQAService()

# 内存降级存储（ChromaDB 不可用时启用）
_all_chunks: List[Dict] = []
_document_count: int = 0

# 初始化标记
_initialized = False


def initialize_services():
    """
    应用启动时初始化所有服务。

    在 main.py 的 lifespan 中调用，确保各模块连接就绪。
    """
    global _initialized

    if _initialized:
        return

    logger.info("=" * 60)
    logger.info("[Registry] 初始化服务模块...")

    # 检查各模块可用性
    chroma_ok = is_chroma_available()
    embed_ok = is_embedding_available()
    minio_ok = is_minio_available()

    logger.info(f"[Registry] ChromaDB:  {'可用' if chroma_ok else '不可用 (内存降级)'}")
    logger.info(f"[Registry] Embedding: {get_embedding_mode()}")
    logger.info(f"[Registry] MinIO:     {'可用' if minio_ok else '不可用 (本地降级)'}")
    logger.info("=" * 60)

    _initialized = True


def add_document_chunks(
    chunks: List[Dict],
    doc_id: str,
    filename: str,
    doc_type: str = "规范",
):
    """
    上传文档后调用，将解析出的 chunk 追加到共享索引。

    流程：
      1. 追加文档元数据标记
      2. 写入 ChromaDB 向量库（主路径）
      3. 追加内存列表（降级路径 / Chroma 第三路备用）

    Args:
        chunks: chunk_clauses() 或文本分句后的 chunk 列表
        doc_id: 文档唯一标识
        filename: 文档名（用于前端溯源展示）
        doc_type: 文档类型（规范 / 图集）
    """
    global _all_chunks, _search_service, _regulation_qa, _document_count

    for ch in chunks:
        ch["metadata"] = ch.get("metadata", {})
        ch["metadata"]["source_doc_id"] = doc_id
        ch["metadata"]["source_filename"] = filename

    # ── 主路径：写入 ChromaDB 向量库 ──
    collection = (
        COLLECTION_REGULATIONS if doc_type == "规范"
        else COLLECTION_ATLAS_NODES
    )
    indexed_count = index_document_chunks(chunks, collection)

    # ── 降级路径：追加内存列表 ──
    _all_chunks.extend(chunks)
    _document_count += 1

    # ── 重建检索器（Hybrid V2）──
    if is_chroma_available():
        retriever = HybridRetrieverV2(chunks=_all_chunks, collection_name=collection)
    else:
        retriever = HybridRetriever(_all_chunks)

    _search_service.load_regulation_chunks(_all_chunks)
    _regulation_qa = RegulationQAService(retriever)

    logger.info(
        f"[Registry] {filename}: {indexed_count}/{len(chunks)} chunks → ChromaDB"
        f" (total: {len(_all_chunks)} chunks / {_document_count} docs)"
    )


def get_search_service() -> SearchService:
    return _search_service


def get_regulation_qa() -> RegulationQAService:
    global _regulation_qa
    if _regulation_qa is None:
        if is_chroma_available():
            retriever = HybridRetrieverV2(chunks=_all_chunks)
        else:
            retriever = HybridRetriever(_all_chunks)
        _regulation_qa = RegulationQAService(retriever)
    return _regulation_qa


def get_atlas_qa() -> AtlasQAService:
    return _atlas_qa


def get_stats() -> dict:
    """获取全局状态统计"""
    return {
        "total_chunks": len(_all_chunks),
        "total_documents": _document_count,
        "chroma": get_chroma_stats(),
        "embedding_mode": get_embedding_mode(),
        "minio_available": is_minio_available(),
        "version": settings.VERSION,
    }


def reset_index():
    """
    清空共享索引（调试用，生产环境需鉴权）。

    同时清理 ChromaDB Collection 和内存列表。
    """
    global _all_chunks, _document_count, _search_service, _regulation_qa, _atlas_qa

    # 清理 ChromaDB
    reset_chroma()

    # 清理内存
    _all_chunks = []
    _document_count = 0
    _search_service = SearchService()
    _atlas_qa = AtlasQAService()

    if is_chroma_available():
        retriever = HybridRetrieverV2(chunks=[])
    else:
        retriever = HybridRetriever([])
    _regulation_qa = RegulationQAService(retriever)

    logger.info("[Registry] 索引已重置 (0 chunks / 0 docs)")

