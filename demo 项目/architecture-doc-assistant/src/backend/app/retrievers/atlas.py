"""
图集检索器
==========
AtlasSearchService: 多维度检索（文本+图片+筛选）。

当前实现使用关键词匹配；Chroma 上线后替换为向量语义检索。
参见 技术开发文档 §4.2.3
"""

import logging
from typing import Any, Dict, List, Optional

from app.retrievers.hybrid import HybridRetriever
from app.utils.llm import is_llm_available, rerank_by_llm

logger = logging.getLogger(__name__)


class AtlasSearchService:
    """图集节点多维度检索"""

    def __init__(self, chunks: Optional[List[Dict]] = None):
        self.chunks = chunks or []
        self.hybrid = HybridRetriever(self.chunks)

    def load_nodes(self, nodes: List[Dict]):
        """加载图集节点数据"""
        self.chunks = nodes
        self.hybrid.load_chunks(nodes)

    def search_nodes(
        self,
        query: Optional[str] = None,
        atlas_code: Optional[str] = None,
        node_id: Optional[str] = None,
        material: Optional[str] = None,
        construction_name: Optional[str] = None,
        page_num: Optional[int] = None,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        图集节点多维度检索

        支持:
          - 语义检索（传入 query）
          - 精确筛选（atlas_code / node_id / material）
          - 纯筛选模式（不传 query）
        """
        logger.info(
            f"[AtlasSearch] query='{query or '(filter only)'}' "
            f"atlas={atlas_code} node={node_id} material={material}"
        )

        # 构建过滤条件
        filters = {}
        if atlas_code:
            filters["atlas_code"] = atlas_code
        if node_id:
            filters["node_id"] = node_id

        if query and self.chunks:
            # 语义检索模式
            results = self.hybrid.retrieve(query=query, filters=filters, top_k=top_k)
            return self._format_results(results)
        elif filters:
            # 纯筛选模式
            filtered = []
            for chunk in self.chunks:
                meta = chunk.get("metadata", {})
                if all(meta.get(k) == v for k, v in filters.items()):
                    filtered.append((1.0, chunk))
            return self._format_results(filtered[:top_k])

        return []

    @staticmethod
    def _format_results(scored: list) -> List[Dict]:
        return [
            {
                "node_id": c[1].get("metadata", {}).get("node_id", ""),
                "node_name": c[1].get("metadata", {}).get("node_name", ""),
                "atlas_code": c[1].get("metadata", {}).get("atlas_code", ""),
                "atlas_title": c[1].get("metadata", {}).get("atlas_title", ""),
                "description": c[1].get("content", ""),
                "materials": c[1].get("metadata", {}).get("materials", []),
                "page_num": c[1].get("metadata", {}).get("page_num", 0),
                "similarity_score": round(c[0], 4),
            }
            for c in scored
        ]
