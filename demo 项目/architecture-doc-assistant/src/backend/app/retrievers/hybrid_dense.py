"""
升级版混合检索器 (ChromaDB + BGE-M3)
====================================
Dense (BGE-M3) + Sparse (Chroma keyword) + RRF 融合 → LLM Rerank。

当 ChromaDB 不可用时，自动降级为原内存关键词 + LLM Rerank 链。
"""

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from app.core.vectordb import (
    search_by_vector,
    search_by_text,
    is_chroma_available,
    COLLECTION_REGULATIONS,
    COLLECTION_ATLAS_NODES,
)
from app.utils.llm import rerank_by_llm, is_llm_available

logger = logging.getLogger(__name__)


class HybridRetrieverV2:
    """
    混合检索器 v2：ChromaDB 稠密 + 关键词 + RRF → LLM Rerank

    三路检索：
      - Dense:  BGE-M3 语义向量搜索 (weight=0.5)
      - Sparse: Chroma 全文关键词检索 (weight=0.3)
      - BM25:   内存关键词匹配（降级时启用, weight=0.2）

    当 ChromaDB 不可用时，退化为原 HybridRetriever 的逻辑。
    """

    def __init__(
        self,
        chunks: Optional[List[Dict]] = None,
        collection_name: str = COLLECTION_REGULATIONS,
    ):
        self.chunks = chunks or []  # 内存降级用
        self.collection_name = collection_name

    def retrieve(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
    ) -> List[Tuple[float, Dict]]:
        """
        混合检索主方法。

        Args:
            query: 用户查询
            filters: 元数据过滤
            top_k: 最终返回数量

        Returns:
            [(score, chunk), ...] 按相关度降序
        """
        logger.info(
            f"[HybridV2] query='{query[:60]}...' collection={self.collection_name}"
        )

        if is_chroma_available():
            return self._chroma_retrieve(query, filters, top_k)
        else:
            return self._fallback_retrieve(query, filters, top_k)

    def _chroma_retrieve(
        self,
        query: str,
        filters: Optional[Dict] = None,
        top_k: int = 5,
    ) -> List[Tuple[float, Dict]]:
        """
        ChromaDB 多路检索 + RRF 融合。

        三路并行:
          1. Dense (BGE-M3 vector): weight=0.5
          2. Sparse (Chroma keyword): weight=0.3
          3. BM25 fallback: weight=0.2 (optional)
        """
        candidate_count = top_k * 4  # 扩大候选集

        # ── 第一路：稠密向量检索 ──
        dense_results = search_by_vector(
            query=query,
            collection_name=self.collection_name,
            top_k=candidate_count,
            filters=filters,
        )

        # ── 第二路：Chroma 全文检索 ──
        sparse_results = search_by_text(
            query=query,
            collection_name=self.collection_name,
            top_k=candidate_count,
            filters=filters,
        )

        # ── 第三路：内存 BM25 降级检索 ──
        bm25_results = self._keyword_search(query, filters, candidate_count)

        # ── RRF 融合 ──
        fused = self._rrf_fusion(
            [dense_results, sparse_results, bm25_results],
            weights=[0.5, 0.3, 0.2],
            k=60,
        )

        logger.info(
            f"[HybridV2] 检索结果: dense={len(dense_results)} "
            f"sparse={len(sparse_results)} bm25={len(bm25_results)} "
            f"fused={len(fused)}"
        )

        # ── LLM Rerank 精排 ──
        if is_llm_available() and len(fused) > 1:
            # LLM Rerank 需要的是 content 文本
            rerank_candidates = [(0.0, {"content": item[1].get("content", "")}) for item in fused[:candidate_count]]
            reranked_content = rerank_by_llm(query, rerank_candidates, top_k)
            # 映射回原始结果
            result = []
            seen = set()
            for score, rc in reranked_content:
                for _, item in fused:
                    key = item.get("chunk_id", item.get("metadata", {}).get("chunk_id", ""))
                    if key and key not in seen:
                        result.append((score, item))
                        seen.add(key)
                        break
                if len(result) >= top_k:
                    break
            return result[:top_k] if result else [(round(f[0], 4), f[1]) for f in fused[:top_k]]
        else:
            return [(round(f[0], 4), f[1]) for f in fused[:top_k]]

    def _fallback_retrieve(
        self,
        query: str,
        filters: Optional[Dict] = None,
        top_k: int = 5,
    ) -> List[Tuple[float, Dict]]:
        """
        ChromaDB 不可用时的降级检索（原 HybridRetriever 逻辑）。
        """
        logger.warning("[HybridV2] ChromaDB 不可用，使用内存关键词检索")

        # 关键词粗筛
        candidates = self._keyword_search(query, filters, top_k * 3)

        # LLM Rerank
        if is_llm_available() and len(candidates) > 1:
            return rerank_by_llm(query, candidates, top_k)
        else:
            return [(round(c[0], 4), c[1]) for c in candidates[:top_k]]

    def _keyword_search(
        self,
        query: str,
        filters: Optional[Dict] = None,
        candidate_count: int = 15,
    ) -> List[Tuple[float, Dict]]:
        """关键词粗筛（内存模式，作为 Chroma 第三路补充）"""
        if not self.chunks:
            return []

        query_terms = set(query.replace("？", "").replace("?", "").strip())
        scored = []

        for chunk in self.chunks:
            meta = chunk.get("metadata", {})
            if filters and not self._match_filters(meta, filters):
                continue

            content = chunk.get("content", "")
            hit_chars = sum(1 for ch in query_terms if ch in content)
            keyword_score = hit_chars / max(len(query_terms), 1)

            clause_id = meta.get("clause_id", "")
            if clause_id and clause_id in query:
                keyword_score += 1.0

            scored.append((keyword_score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:candidate_count]

    @staticmethod
    def _match_filters(meta: Dict, filters: Dict) -> bool:
        """检查元数据过滤条件"""
        for key, value in filters.items():
            if key == "status":
                allowed = value if isinstance(value, list) else [value]
                if meta.get("status") not in allowed:
                    return False
            if key == "standard_code" and value not in meta.get("standard_code", ""):
                return False
        return True

    @staticmethod
    def _rrf_fusion(
        results_list: List[List[Tuple[float, Dict]]],
        weights: List[float],
        k: int = 60,
    ) -> List[Tuple[float, Dict]]:
        """
        Reciprocal Rank Fusion 多路融合。

        score(doc) = sum( weight_i * 1 / (k + rank_i + 1) )

        返回融合后按 RRF score 降序排列的结果。
        """
        scores: Dict[str, Tuple[float, Dict]] = defaultdict(lambda: (0.0, {}))

        for results, weight in zip(results_list, weights):
            for rank, (_, chunk) in enumerate(results):
                key = chunk.get("chunk_id", chunk.get("metadata", {}).get("chunk_id", str(rank)))
                current_score, _ = scores[key]
                scores[key] = (
                    current_score + weight * (1.0 / (k + rank + 1)),
                    chunk,
                )

        sorted_items = sorted(scores.values(), key=lambda x: x[0], reverse=True)
        return sorted_items

    def load_chunks(self, chunks: List[Dict]):
        """加载内存 chunk（用于降级和 BM25 补充检索）"""
        self.chunks = chunks
