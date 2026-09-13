"""基于 DashScope TextReRank API 的交叉编码器重排序服务。

提供同步和异步两种调用方式，支持优雅降级（API 不可用时跳过重排序）。
KB 精排和 Web 精排由两个独立开关控制，可分别启用。

Usage:
    from agent.reranker import get_reranker

    reranker = get_reranker()

    # Web 搜索精排
    if reranker.web_enabled:
        ranked = reranker.rerank(query="AI芯片趋势", documents=docs)

    # KB 检索精排
    if reranker.kb_enabled:
        ranked = reranker.rerank(query=topic, documents=facts)
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Optional

from dashscope import TextReRank
from loguru import logger


class RerankerService:
    """交叉编码器重排序服务 — 封装 DashScope TextReRank API。

    每个接入点（KB / Web）有独立开关，调用方在调用 rerank() 前自行检查。
    rerank() 本身不检查开关 — 它只负责调用 API 并返回结果。
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        kb_enabled: bool | None = None,
        web_enabled: bool | None = None,
        top_k: int | None = None,
        min_score: float | None = None,
    ):
        # 配置优先级：构造参数 > 环境变量 > 默认值
        self.model = model or os.getenv("RERANKER_MODEL", "gte-rerank")
        self.api_key = (
            api_key
            or os.getenv("RERANKER_API_KEY")
            or os.getenv("DASHSCOPE_API_KEY")
            or os.getenv("APP_TOKEN", "")
        )

        # KB 精排开关：构造参数 > RERANKER_KB_ENABLED > 默认 false
        if kb_enabled is not None:
            self.kb_enabled = kb_enabled
        else:
            raw = os.getenv("RERANKER_KB_ENABLED", "false")
            self.kb_enabled = raw.lower() in ("true", "1", "yes")

        # Web 精排开关：构造参数 > RERANKER_WEB_ENABLED > 默认 false
        if web_enabled is not None:
            self.web_enabled = web_enabled
        else:
            raw = os.getenv("RERANKER_WEB_ENABLED", "false")
            self.web_enabled = raw.lower() in ("true", "1", "yes")

        self.top_k = top_k if top_k is not None else int(os.getenv("RERANKER_TOP_K", "5"))
        self.min_score = min_score if min_score is not None else float(os.getenv("RERANKER_MIN_SCORE", "0.0"))

        if self.kb_enabled or self.web_enabled:
            logger.info(
                f"[Reranker] 已初始化 model={self.model} top_k={self.top_k} "
                f"min_score={self.min_score} kb={self.kb_enabled} web={self.web_enabled}"
            )
        else:
            logger.debug("[Reranker] 已初始化（KB 和 Web 精排均已禁用）")

    # ── public API ────────────────────────────────────────────────────

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> list[dict]:
        """对文档列表进行语义重排序。

        Args:
            query: 用户查询文本。
            documents: 待评分文档的文本列表。
            top_k: 保留前 N 条。未指定时使用实例级别 self.top_k。
            min_score: 最低相关度阈值。未指定时使用实例级别 self.min_score。

        Returns:
            [{"index": int, "document": str, "score": float}, ...]
            按 score 降序排列。降级时返回全部文档原始顺序，score=0.0。
        """
        if not documents:
            return []

        effective_top_k = top_k if top_k is not None else self.top_k
        effective_min_score = min_score if min_score is not None else self.min_score

        if not self.api_key:
            logger.warning("[Reranker] API Key 未配置，降级为直通")
            return self._fallback(documents)

        # ── 3 次重试 ──────────────────────────────────────────────
        last_error = None
        for attempt in range(3):
            try:
                response = TextReRank.call(
                    model=self.model,
                    query=query,
                    documents=documents,
                    top_n=effective_top_k if effective_top_k < len(documents) else None,
                    api_key=self.api_key,
                )

                if response.status_code == 200:
                    return self._extract_results(
                        response, documents, effective_top_k, effective_min_score
                    )

                # HTTP 错误分类
                if response.status_code == 429:
                    last_error = f"速率限制(429)"
                    delay = 5 * (attempt + 1)
                elif response.status_code in (401, 403):
                    logger.error(
                        f"[Reranker] 认证/权限错误 {response.status_code}: {response.message}"
                    )
                    return self._fallback(documents)
                elif 500 <= response.status_code < 600:
                    last_error = f"服务端错误({response.status_code})"
                    delay = 2.0 * (attempt + 1)
                else:
                    last_error = f"未知错误({response.status_code}): {response.message}"
                    delay = 2.0 * (attempt + 1)

                if attempt < 2:
                    logger.warning(
                        f"[Reranker] {last_error}，{delay:.1f}s 后重试 ({attempt + 1}/3)"
                    )
                    time.sleep(delay)

            except Exception as exc:
                error_msg = str(exc)
                # 网络错误
                if "429" in error_msg:
                    delay = 5 * (attempt + 1)
                else:
                    delay = 2.0 * (attempt + 1)

                if attempt < 2:
                    logger.warning(
                        f"[Reranker] 瞬时错误 ({type(exc).__name__}: {exc})，"
                        f"{delay:.1f}s 后重试 ({attempt + 1}/3)"
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"[Reranker] 重试 3 次全部失败，降级为直通: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    last_error = str(exc)

        # 重试耗尽
        if last_error:
            logger.warning(f"[Reranker] 降级直通，原因: {last_error}")
        return self._fallback(documents)

    async def arerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> list[dict]:
        """异步版本的 rerank() — 通过 asyncio.to_thread 包装同步调用。"""
        return await asyncio.to_thread(
            self.rerank,
            query=query,
            documents=documents,
            top_k=top_k,
            min_score=min_score,
        )

    # ── private helpers ───────────────────────────────────────────────

    def _extract_results(
        self,
        response,
        documents: list[str],
        top_k: int,
        min_score: float,
    ) -> list[dict]:
        """从 API 响应中提取并格式化结果。"""
        results = response.output.results if response.output else []
        if not results:
            logger.info("[Reranker] API 返回空结果，降级为直通")
            return self._fallback(documents)

        ranked = []
        for r in results:
            score = r.relevance_score
            if score < min_score:
                continue
            idx = r.index
            if idx < len(documents):
                ranked.append({
                    "index": idx,
                    "document": documents[idx],
                    "score": round(score, 4),
                })

        # 结果已按 API 返回顺序（score 降序），cut 到 top_k
        if len(ranked) > top_k:
            ranked = ranked[:top_k]

        if ranked:
            scores = [r["score"] for r in ranked[:3]]
            logger.info(
                f"[Reranker] 精排完成: {len(documents)} → {len(ranked)} docs, "
                f"top scores={scores}"
            )

        return ranked

    def _fallback(self, documents: list[str]) -> list[dict]:
        """降级：返回原始文档顺序，score=0.0。"""
        return [
            {"index": i, "document": doc, "score": 0.0}
            for i, doc in enumerate(documents)
        ]


# ── 模块级单例 ─────────────────────────────────────────────────────────

_reranker: RerankerService | None = None


def get_reranker() -> RerankerService:
    """获取全局 RerankerService 单例（延迟初始化）。"""
    global _reranker
    if _reranker is None:
        _reranker = RerankerService()
    return _reranker
