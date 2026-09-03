"""
检索服务
========
混合检索编排：关键词粗筛 + LLM Rerank 精排。

当 Chroma + BGE-M3 就绪后，通过依赖注入切换为 Dense+Sparse+BM25 全链路。
"""

import logging
from typing import Optional

from app.retrievers.hybrid import HybridRetriever
from app.retrievers.atlas import AtlasSearchService

logger = logging.getLogger(__name__)


class SearchService:
    """规范 + 图集统一检索入口"""

    def __init__(self):
        self._regulation_retriever: Optional[HybridRetriever] = None
        self._atlas_searcher: Optional[AtlasSearchService] = None

    def load_regulation_chunks(self, chunks: list):
        """加载规范条款 chunk 集合"""
        self._regulation_retriever = HybridRetriever(chunks)

    def load_atlas_nodes(self, nodes: list):
        """加载图集节点数据"""
        self._atlas_searcher = AtlasSearchService(nodes)

    def search_regulations(
        self,
        query: str,
        filters: dict | None = None,
        search_mode: str = "hybrid",
        top_k: int = 10,
    ) -> dict:
        """
        规范条款混合检索。

        模式:
          - semantic: LLM Rerank（当前实现）
          - keyword: 纯关键词排序
          - hybrid: 关键词 + LLM Rerank（默认）

        Returns:
            {"total": int, "results": [...]}
        """
        logger.info(f"[SearchService] regulation query='{query[:50]}...' mode={search_mode}")

        if not self._regulation_retriever:
            logger.warning("[SearchService] regulation chunks not loaded")
            return {"total": 0, "results": []}

        ranked = self._regulation_retriever.retrieve(
            query=query, filters=filters, top_k=top_k
        )

        results = [
            {
                "clause_id": c[1].get("metadata", {}).get("clause_id", ""),
                "clause_title": c[1].get("metadata", {}).get("chapter", ""),
                "content": c[1].get("content", ""),
                "standard_code": c[1].get("metadata", {}).get("standard_code", ""),
                "standard_title": c[1].get("metadata", {}).get("standard_title", ""),
                "chapter_path": c[1].get("metadata", {}).get("chapter", ""),
                "page_num": c[1].get("metadata", {}).get("page_num"),
                "status": c[1].get("metadata", {}).get("status", "有效"),
                "score": round(c[0], 4),
            }
            for c in ranked
        ]

        return {"total": len(results), "results": results}

    def search_atlas(
        self,
        query: str | None,
        atlas_code: str | None = None,
        node_id: str | None = None,
        material: str | None = None,
    ) -> dict:
        """图集节点多维度检索"""
        logger.info(f"[SearchService] atlas query='{query or '(filter only)'}'")

        if not self._atlas_searcher:
            return {"total": 0, "results": []}

        results = self._atlas_searcher.search_nodes(
            query=query,
            atlas_code=atlas_code,
            node_id=node_id,
            material=material,
        )

        return {"total": len(results), "results": results}
