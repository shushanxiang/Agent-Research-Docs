"""Tests for FactStore — Milvus-backed fact storage and retrieval."""

import json
import pytest
from unittest.mock import MagicMock, patch, call


def _make_result(index: int, score: float):
    """构造模拟的 ReRankResult。"""
    r = MagicMock()
    r.index = index
    r.relevance_score = score
    r.document = {}
    return r


class TestFactStoreInit:
    def test_default_init(self):
        from agent.kb.fact_store import FactStore

        with patch("agent.kb.fact_store.MilvusClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.has_collection.return_value = True
            mock_client_cls.return_value = mock_client

            store = FactStore()
            assert store.collection == "research_facts"
            assert store.uri == "http://localhost:19530"

    def test_custom_uri_and_collection(self):
        from agent.kb.fact_store import FactStore

        with patch("agent.kb.fact_store.MilvusClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.has_collection.return_value = True
            mock_client_cls.return_value = mock_client

            store = FactStore(uri="http://custom:19530", collection="custom_facts")
            assert store.uri == "http://custom:19530"
            assert store.collection == "custom_facts"


class TestFactStoreAddFacts:
    def test_add_facts_embeds_and_inserts(self):
        from agent.kb.fact_store import FactStore

        with patch("agent.kb.fact_store.MilvusClient") as mock_client_cls, \
             patch("agent.kb.fact_store.requests.post") as mock_post:
            # Mock MilvusClient
            mock_client = MagicMock()
            mock_client.has_collection.return_value = True
            mock_client.insert.return_value = {"insert_count": 2}
            mock_client_cls.return_value = mock_client

            # Mock embedding API
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {
                "data": [
                    {"embedding": [0.1] * 1024, "index": 0},
                    {"embedding": [0.2] * 1024, "index": 1},
                ]
            }
            mock_post.return_value = mock_resp

            store = FactStore()
            facts = [
                {"fact": "AI芯片市场达500亿美元", "source_url": "https://example.com/1", "confidence": 0.9},
                {"fact": "NVIDIA占80%份额", "source_url": "https://example.com/2", "confidence": 0.85},
            ]
            count = store.add_facts(facts)

            assert count == 2
            mock_client.insert.assert_called_once()
            mock_post.assert_called_once()

    def test_add_facts_empty_list(self):
        from agent.kb.fact_store import FactStore

        with patch("agent.kb.fact_store.MilvusClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.has_collection.return_value = True
            mock_client_cls.return_value = mock_client

            store = FactStore()
            result = store.add_facts([])
            assert result == 0


class TestFactStoreQuery:
    def test_query_returns_hits(self):
        from agent.kb.fact_store import FactStore

        with patch("agent.kb.fact_store.MilvusClient") as mock_client_cls, \
             patch("agent.kb.fact_store.requests.post") as mock_post:
            mock_client = MagicMock()
            mock_client.has_collection.return_value = True
            mock_client.search.return_value = [[
                {
                    "entity": {
                        "fact_text": "AI芯片市场500亿美元",
                        "source_url": "https://example.com",
                        "research_topic": "AI芯片",
                        "confidence": 0.9,
                        "created_at": 1700000000,
                    },
                    "distance": 0.15,
                }
            ]]
            mock_client_cls.return_value = mock_client

            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {
                "data": [{"embedding": [0.1] * 1024, "index": 0}]
            }
            mock_post.return_value = mock_resp

            store = FactStore()
            results = store.query("AI芯片市场", top_k=10)

            assert len(results) == 1
            assert results[0]["fact"] == "AI芯片市场500亿美元"
            assert results[0]["relevance"] == 0.85  # 1.0 - 0.15

    def test_query_empty_results(self):
        from agent.kb.fact_store import FactStore

        with patch("agent.kb.fact_store.MilvusClient") as mock_client_cls, \
             patch("agent.kb.fact_store.requests.post") as mock_post:
            mock_client = MagicMock()
            mock_client.has_collection.return_value = True
            mock_client.search.return_value = [[]]
            mock_client_cls.return_value = mock_client

            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {
                "data": [{"embedding": [0.1] * 1024, "index": 0}]
            }
            mock_post.return_value = mock_resp

            store = FactStore()
            results = store.query("no results", top_k=10)

            assert results == []

    def test_query_filters_by_min_confidence(self):
        from agent.kb.fact_store import FactStore

        with patch("agent.kb.fact_store.MilvusClient") as mock_client_cls, \
             patch("agent.kb.fact_store.requests.post") as mock_post:
            mock_client = MagicMock()
            mock_client.has_collection.return_value = True
            mock_client.search.return_value = [[
                {
                    "entity": {
                        "fact_text": "low confidence fact",
                        "source_url": "https://example.com",
                        "research_topic": "AI",
                        "confidence": 0.5,
                        "created_at": 1700000000,
                    },
                    "distance": 0.1,
                },
                {
                    "entity": {
                        "fact_text": "high confidence fact",
                        "source_url": "https://example.com",
                        "research_topic": "AI",
                        "confidence": 0.9,
                        "created_at": 1700000000,
                    },
                    "distance": 0.2,
                },
            ]]
            mock_client_cls.return_value = mock_client

            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {
                "data": [{"embedding": [0.1] * 1024, "index": 0}]
            }
            mock_post.return_value = mock_resp

            store = FactStore()
            results = store.query("AI", top_k=10, min_confidence=0.7)

            assert len(results) == 1
            assert results[0]["fact"] == "high confidence fact"


class TestFactStoreEmbed:
    def test_embed_retry_on_429(self):
        from agent.kb.fact_store import FactStore

        with patch("agent.kb.fact_store.MilvusClient") as mock_client_cls, \
             patch("agent.kb.fact_store.requests.post") as mock_post, \
             patch("agent.kb.fact_store.time.sleep") as mock_sleep:
            mock_client = MagicMock()
            mock_client.has_collection.return_value = True
            mock_client_cls.return_value = mock_client

            # Fail twice with 429, succeed on third
            fail_resp = MagicMock()
            fail_resp.status_code = 429
            fail_resp.raise_for_status.side_effect = __import__('requests').HTTPError(response=fail_resp)

            success_resp = MagicMock()
            success_resp.raise_for_status.return_value = None
            success_resp.json.return_value = {
                "data": [{"embedding": [0.1] * 1024, "index": 0}]
            }

            mock_post.side_effect = [fail_resp, fail_resp, success_resp]

            store = FactStore()
            result = store._embed(["test text"])

            assert result is not None
            assert mock_post.call_count == 3
            assert mock_sleep.call_count >= 2  # waited before retries

    def test_embed_all_retries_exhausted(self):
        from agent.kb.fact_store import FactStore
        from agent.exceptions import KBEmbeddingError

        with patch("agent.kb.fact_store.MilvusClient") as mock_client_cls, \
             patch("agent.kb.fact_store.requests.post") as mock_post, \
             patch("agent.kb.fact_store.time.sleep"):
            mock_client = MagicMock()
            mock_client.has_collection.return_value = True
            mock_client_cls.return_value = mock_client

            fail_resp = MagicMock()
            fail_resp.status_code = 500
            fail_resp.raise_for_status.side_effect = __import__('requests').HTTPError(response=fail_resp)
            mock_post.return_value = fail_resp

            store = FactStore()
            with pytest.raises(KBEmbeddingError, match="500"):
                store._embed(["test text"])


class TestFactStoreEnsureCollection:
    def test_existing_collection_skips_creation(self):
        from agent.kb.fact_store import FactStore

        with patch("agent.kb.fact_store.MilvusClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.has_collection.return_value = True
            mock_client_cls.return_value = mock_client

            FactStore()
            mock_client.create_collection.assert_not_called()

    def test_new_collection_created_with_index(self):
        from agent.kb.fact_store import FactStore

        with patch("agent.kb.fact_store.MilvusClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.has_collection.return_value = False
            mock_client_cls.return_value = mock_client

            FactStore()
            mock_client.create_collection.assert_called_once()
            mock_client.create_index.assert_called_once()


class TestFactStoreStats:
    def test_stats_returns_row_count(self):
        from agent.kb.fact_store import FactStore

        with patch("agent.kb.fact_store.MilvusClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.has_collection.return_value = True
            mock_client.get_collection_stats.return_value = {"row_count": 42}
            mock_client_cls.return_value = mock_client

            store = FactStore()
            stats = store.stats()
            assert stats["row_count"] == 42
            assert stats["collection"] == "research_facts"


class TestFactStoreQueryWithReranker:
    """KB 精排集成测试 — 验证 FactStore.query() 与 RerankerService 的协作。"""

    @pytest.fixture(autouse=True)
    def _patch_reranker(self):
        """重置 reranker 单例，确保测试隔离。"""
        import agent.reranker as mod
        import agent.kb.fact_store as fs_mod
        mod._reranker = None
        yield
        mod._reranker = None

    def _make_milvus_hits(self, *fact_texts):
        """构造 Milvus 搜索返回的多条命中记录。"""
        hits = []
        for text in fact_texts:
            hits.append({
                "entity": {
                    "fact_text": text,
                    "source_url": "https://example.com",
                    "research_topic": "AI",
                    "confidence": 0.9,
                    "created_at": 1700000000,
                    "fact_category": "strategy",
                },
                "distance": 0.15,
            })
        return hits

    def test_reranker_disabled_by_default(self):
        """默认 KB 精排关闭，Milvus 距离决定 relevance。"""
        from agent.kb.fact_store import FactStore

        with patch("agent.kb.fact_store.MilvusClient") as mock_client_cls, \
             patch("agent.kb.fact_store.requests.post") as mock_post:
            mock_client = MagicMock()
            mock_client.has_collection.return_value = True
            mock_client.search.return_value = [self._make_milvus_hits(
                "AI芯片市场规模500亿美元", "NVIDIA市场份额分析"
            )]
            mock_client_cls.return_value = mock_client

            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {
                "data": [{"embedding": [0.1] * 1024, "index": 0}]
            }
            mock_post.return_value = mock_resp

            store = FactStore()
            results = store.query("AI芯片趋势", top_k=10)

            # reranker 禁用时，relevance 来自 Milvus 距离（1.0 - 0.15 = 0.85）
            assert len(results) == 2
            assert results[0]["relevance"] == 0.85

    def test_reranker_kb_enabled_reorders_results(self, monkeypatch):
        """KB 精排开启时，reranker 分数覆盖 relevance 并重排。"""
        monkeypatch.setenv("APP_TOKEN", "sk-test")
        monkeypatch.setenv("RERANKER_KB_ENABLED", "true")

        from agent.kb.fact_store import FactStore
        import agent.reranker as mod
        mod._reranker = None

        with patch("agent.kb.fact_store.MilvusClient") as mock_client_cls, \
             patch("agent.kb.fact_store.requests.post") as mock_post, \
             patch("agent.reranker.TextReRank.call") as mock_rerank_call:
            mock_client = MagicMock()
            mock_client.has_collection.return_value = True
            mock_client.search.return_value = [self._make_milvus_hits(
                "不相关的天气信息", "AI芯片发展趋势分析报告", "今天股市行情"
            )]
            mock_client_cls.return_value = mock_client

            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {
                "data": [{"embedding": [0.1] * 1024, "index": 0}]
            }
            mock_post.return_value = mock_resp

            # 模拟 reranker：index=1 的 "AI芯片发展趋势..." 得分最高
            mock_rerank_resp = MagicMock()
            mock_rerank_resp.status_code = 200
            mock_rerank_resp.output.results = [
                _make_result(1, 0.95),  # "AI芯片发展趋势分析报告"
                _make_result(2, 0.45),  # "今天股市行情"
                _make_result(0, 0.12),  # "不相关的天气信息"
            ]
            mock_rerank_call.return_value = mock_rerank_resp

            store = FactStore()
            results = store.query("AI芯片趋势", top_k=10)

            # 重排后 relevance 使用 rerank 分数
            assert len(results) == 3
            assert results[0]["fact"] == "AI芯片发展趋势分析报告"
            assert results[0]["relevance"] == 0.95
            assert results[1]["fact"] == "今天股市行情"
            assert results[1]["relevance"] == 0.45
            assert results[2]["fact"] == "不相关的天气信息"
            assert results[2]["relevance"] == 0.12

    def test_reranker_fails_gracefully_in_query(self, monkeypatch):
        """reranker 失败时，降级回 Milvus 距离排序。"""
        monkeypatch.setenv("APP_TOKEN", "sk-test")
        monkeypatch.setenv("RERANKER_KB_ENABLED", "true")

        from agent.kb.fact_store import FactStore
        import agent.reranker as mod
        mod._reranker = None

        with patch("agent.kb.fact_store.MilvusClient") as mock_client_cls, \
             patch("agent.kb.fact_store.requests.post") as mock_post, \
             patch("agent.reranker.TextReRank.call", side_effect=ConnectionError("网络不通")):
            mock_client = MagicMock()
            mock_client.has_collection.return_value = True
            mock_client.search.return_value = [self._make_milvus_hits(
                "AI芯片市场报告", "无关内容"
            )]
            mock_client_cls.return_value = mock_client

            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {
                "data": [{"embedding": [0.1] * 1024, "index": 0}]
            }
            mock_post.return_value = mock_resp

            store = FactStore()
            results = store.query("AI芯片趋势", top_k=10)

            # 降级后仍有结果，relevance 来自 Milvus 距离
            assert len(results) == 2
            assert results[0]["relevance"] == 0.85
