"""
混合检索器
==========
HybridRetriever: 关键词粗筛 + LLM Rerank 精排。

在当前阶段（尚未接入 Chroma + BGE-M3），使用基于字符重叠度的关键词检索
作为第一轮粗筛，再用 LLM Rerank 做精排。当 Chroma 向量库就绪后，
可无缝切换为 Dense + Sparse + BM25 → RRF → Rerank 全链路。

参见 技术开发文档 §4.2.2
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from app.utils.llm import rerank_by_llm, is_llm_available

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    混合检索器：粗筛 + 精排。

    当前实现：keyword overlap → LLM Rerank
    未来实现：Dense(0.5) + Sparse(0.3) + BM25(0.2) → RRF → Cross-Encoder Rerank
    """

    def __init__(self, chunks: Optional[List[Dict]] = None):
        """
        Args:
            chunks: 预加载的文档 chunk 列表。生产环境将从 Chroma 实时读取。
        """
        self.chunks = chunks or []

    def load_chunks(self, chunks: List[Dict]):
        """加载新的 chunk 集合（对齐 Chroma 向量库切换）"""
        self.chunks = chunks

    def retrieve(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
    ) -> List[Tuple[float, Dict]]:
        """
        混合检索主方法。

        Args:
            query: 用户查询文本
            filters: 元数据过滤条件 {"status": "有效", "standard_code": "GB 55037"}
            top_k: 返回数量

        Returns:
            [(score, chunk), ...] 按相关度降序
        """
        if not self.chunks:
            logger.warning("[HybridRetriever] chunk 集合为空")
            return []

        logger.info(f"[HybridRetriever] query='{query[:50]}...' k={top_k}")

        # ── 第一轮：关键词粗筛 ──
        candidates = self._keyword_filter(query, filters, top_k * 3)

        # ── 第二轮：LLM Rerank 精排 ──
        if is_llm_available() and len(candidates) > 1:
            ranked = rerank_by_llm(query, candidates, top_k)
        else:
            ranked = [(c[0], c[1]) for c in candidates[:top_k]]

        return ranked[:top_k]

    def _keyword_filter(
        self,
        query: str,
        filters: Optional[Dict] = None,
        candidate_count: int = 15,
    ) -> List[Tuple[float, Dict]]:
        """
        关键词粗筛：基于字符重叠度 + 条款号匹配。

        当接入 Redis BM25 后可替换为更精确的全文检索。
        """
        query_terms = set(query.replace("？", "").replace("?", "").strip())
        scored = []

        for chunk in self.chunks:
            # 元数据过滤
            meta = chunk.get("metadata", {})
            if filters:
                if not self._match_filters(meta, filters):
                    continue

            content = chunk.get("content", "")

            # 字符重叠评分
            hit_chars = sum(1 for ch in query_terms if ch in content)
            keyword_score = hit_chars / max(len(query_terms), 1)

            # 条款号精确匹配加分
            clause_id = meta.get("clause_id", "")
            if clause_id and clause_id in query:
                keyword_score += 1.0

            scored.append((keyword_score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:candidate_count]

    @staticmethod
    def _match_filters(meta: Dict, filters: Dict) -> bool:
        """检查 chunk 元数据是否满足过滤条件"""
        for key, value in filters.items():
            if key == "status" and meta.get("status") not in (value if isinstance(value, list) else [value]):
                return False
            if key == "standard_code" and value not in meta.get("standard_code", ""):
                return False
        return True

    def reciprocal_rank_fusion(
        self,
        results_list: List[List[dict]],
        weights: List[float],
        k: int = 60,
    ) -> List[dict]:
        """
        RRF 倒数排名融合算法（预留给 Chroma 多路检索）。

        score(doc) = sum( weight_i * 1 / (k + rank_i + 1) )
        """
        scores: Dict[str, float] = {}
        for results, weight in zip(results_list, weights):
            for rank, doc in enumerate(results):
                doc_id = doc.get("id", doc.get("metadata", {}).get("id", str(rank)))
                scores[doc_id] = scores.get(doc_id, 0) + weight * (1 / (k + rank + 1))

        sorted_ids = sorted(scores, key=scores.get, reverse=True)
        # Chroma 上线后通过 ID 反查文档
        return []
