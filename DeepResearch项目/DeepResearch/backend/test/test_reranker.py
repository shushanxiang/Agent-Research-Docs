"""RerankerService 单元测试。

全部 mock dashscope.TextReRank.call，无真实 API 调用。
"""

import pytest
from unittest import mock
from agent.reranker import RerankerService, get_reranker


class TestRerankerServiceInit:
    """初始化与配置优先级测试。"""

    def test_default_both_disabled(self):
        """默认情况下 KB 和 Web 精排均关闭。"""
        s = RerankerService()
        assert s.kb_enabled is False
        assert s.web_enabled is False

    def test_default_model(self):
        s = RerankerService()
        assert s.model == "gte-rerank"

    def test_default_top_k_and_min_score(self):
        s = RerankerService()
        assert s.top_k == 5
        assert s.min_score == 0.0

    def test_kb_enabled_via_env(self, monkeypatch):
        monkeypatch.setenv("RERANKER_KB_ENABLED", "true")
        s = RerankerService()
        assert s.kb_enabled is True
        assert s.web_enabled is False  # 互不影响

    def test_web_enabled_via_env(self, monkeypatch):
        monkeypatch.setenv("RERANKER_WEB_ENABLED", "1")
        s = RerankerService()
        assert s.web_enabled is True
        assert s.kb_enabled is False

    def test_both_enabled_via_env(self, monkeypatch):
        monkeypatch.setenv("RERANKER_KB_ENABLED", "yes")
        monkeypatch.setenv("RERANKER_WEB_ENABLED", "true")
        s = RerankerService()
        assert s.kb_enabled is True
        assert s.web_enabled is True

    def test_constructor_overrides_env(self, monkeypatch):
        monkeypatch.setenv("RERANKER_KB_ENABLED", "true")
        s = RerankerService(kb_enabled=False)
        assert s.kb_enabled is False

    def test_constructor_params_override_defaults(self):
        s = RerankerService(
            model="custom-model",
            api_key="sk-test",
            kb_enabled=True,
            web_enabled=True,
            top_k=10,
            min_score=0.5,
        )
        assert s.model == "custom-model"
        assert s.api_key == "sk-test"
        assert s.kb_enabled is True
        assert s.web_enabled is True
        assert s.top_k == 10
        assert s.min_score == 0.5

    def test_api_key_fallback_chain(self, monkeypatch):
        # 无任何 KEY 环境变量时，api_key 为空字符串
        monkeypatch.delenv("RERANKER_API_KEY", raising=False)
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        monkeypatch.delenv("APP_TOKEN", raising=False)
        s = RerankerService()
        assert s.api_key == ""

    def test_api_key_uses_dashscope_first(self, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-dash")
        monkeypatch.setenv("APP_TOKEN", "sk-app")
        s = RerankerService()
        assert s.api_key == "sk-dash"

    def test_api_key_falls_back_to_app_token(self, monkeypatch):
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        monkeypatch.setenv("APP_TOKEN", "sk-app")
        s = RerankerService()
        assert s.api_key == "sk-app"

    def test_reranker_api_key_takes_priority(self, monkeypatch):
        monkeypatch.setenv("RERANKER_API_KEY", "sk-rerank")
        monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-dash")
        s = RerankerService()
        assert s.api_key == "sk-rerank"


class TestRerankerServiceRerank:
    """正常评分排序测试。"""

    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        monkeypatch.setenv("APP_TOKEN", "sk-test")

    def test_rerank_returns_scored_and_sorted(self):
        docs = ["关于AI芯片市场", "今天天气很好", "AI芯片发展趋势"]
        mock_response = mock.Mock()
        mock_response.status_code = 200
        # gte-rerank 返回 relevance_score 降序
        mock_response.output.results = [
            _make_result(2, 0.95),  # "AI芯片发展趋势"
            _make_result(0, 0.87),  # "关于AI芯片市场"
            _make_result(1, 0.12),  # "今天天气很好"
        ]

        with mock.patch("agent.reranker.TextReRank.call", return_value=mock_response):
            s = RerankerService()
            ranked = s.rerank(query="AI芯片趋势", documents=docs)

        assert len(ranked) == 3
        assert ranked[0]["index"] == 2
        assert ranked[0]["score"] == 0.95
        assert ranked[0]["document"] == "AI芯片发展趋势"
        assert ranked[1]["index"] == 0
        assert ranked[2]["index"] == 1

    def test_rerank_respects_top_k(self):
        docs = ["A", "B", "C", "D", "E", "F"]
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.output.results = [
            _make_result(i, 1.0 - i * 0.1) for i in range(6)
        ]

        with mock.patch("agent.reranker.TextReRank.call", return_value=mock_response):
            s = RerankerService(top_k=3)
            ranked = s.rerank(query="test", documents=docs)

        assert len(ranked) == 3

    def test_rerank_respects_min_score(self):
        docs = ["A", "B", "C"]
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.output.results = [
            _make_result(0, 0.95),
            _make_result(1, 0.45),
            _make_result(2, 0.30),
        ]

        with mock.patch("agent.reranker.TextReRank.call", return_value=mock_response):
            s = RerankerService(min_score=0.5)
            ranked = s.rerank(query="test", documents=docs)

        assert len(ranked) == 1
        assert ranked[0]["index"] == 0

    def test_rerank_override_top_k_per_call(self):
        docs = ["A", "B", "C", "D", "E"]
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.output.results = [_make_result(i, 0.9 - i * 0.1) for i in range(5)]

        with mock.patch("agent.reranker.TextReRank.call", return_value=mock_response):
            s = RerankerService(top_k=5)
            ranked = s.rerank(query="test", documents=docs, top_k=2)

        assert len(ranked) == 2

    def test_empty_documents_returns_empty(self):
        s = RerankerService()
        ranked = s.rerank(query="test", documents=[])
        assert ranked == []

    def test_no_api_key_fallback(self, monkeypatch):
        monkeypatch.delenv("APP_TOKEN", raising=False)
        docs = ["A", "B"]
        s = RerankerService()
        ranked = s.rerank(query="test", documents=docs)
        # 降级：返回原始顺序
        assert len(ranked) == 2
        assert ranked[0]["index"] == 0
        assert ranked[0]["score"] == 0.0


class TestRerankerServiceErrorHandling:
    """错误场景下的优雅降级测试。"""

    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        monkeypatch.setenv("APP_TOKEN", "sk-test")

    def test_http_500_returns_fallback(self):
        docs = ["A", "B", "C"]
        mock_response = mock.Mock()
        mock_response.status_code = 500
        mock_response.message = "Internal Server Error"

        with mock.patch("agent.reranker.TextReRank.call", return_value=mock_response):
            s = RerankerService()
            ranked = s.rerank(query="test", documents=docs)

        assert len(ranked) == 3
        for r in ranked:
            assert r["score"] == 0.0
        # 原始顺序保持
        assert [r["index"] for r in ranked] == [0, 1, 2]

    def test_http_401_no_retry_fallback(self):
        docs = ["A"]
        mock_response = mock.Mock()
        mock_response.status_code = 401

        with mock.patch("agent.reranker.TextReRank.call", return_value=mock_response):
            s = RerankerService()
            ranked = s.rerank(query="test", documents=docs)

        assert len(ranked) == 1
        assert ranked[0]["score"] == 0.0

    def test_http_429_retries_and_falls_back(self):
        docs = ["A"]
        mock_response = mock.Mock()
        mock_response.status_code = 429

        with mock.patch(
            "agent.reranker.TextReRank.call", return_value=mock_response
        ) as mock_call:
            with mock.patch("agent.reranker.time.sleep", return_value=None):
                s = RerankerService()
                ranked = s.rerank(query="test", documents=docs)

        # 3 次重试
        assert mock_call.call_count == 3
        assert len(ranked) == 1
        assert ranked[0]["score"] == 0.0

    def test_http_429_recovers_on_retry(self):
        docs = ["A", "B"]
        fail_response = mock.Mock()
        fail_response.status_code = 429

        ok_response = mock.Mock()
        ok_response.status_code = 200
        ok_response.output.results = [
            _make_result(1, 0.8),
            _make_result(0, 0.6),
        ]

        with mock.patch(
            "agent.reranker.TextReRank.call",
            side_effect=[fail_response, ok_response],
        ) as mock_call:
            with mock.patch("agent.reranker.time.sleep", return_value=None):
                s = RerankerService()
                ranked = s.rerank(query="test", documents=docs)

        assert mock_call.call_count == 2
        assert ranked[0]["index"] == 1
        assert ranked[0]["score"] == 0.8

    def test_network_error_fallback(self):
        docs = ["A"]
        with mock.patch(
            "agent.reranker.TextReRank.call",
            side_effect=ConnectionError("网络不可达"),
        ):
            with mock.patch("agent.reranker.time.sleep", return_value=None):
                s = RerankerService()
                ranked = s.rerank(query="test", documents=docs)

        assert len(ranked) == 1
        assert ranked[0]["score"] == 0.0

    def test_unexpected_exception_fallback(self):
        docs = ["A"]
        with mock.patch(
            "agent.reranker.TextReRank.call",
            side_effect=ValueError("意外错误"),
        ):
            with mock.patch("agent.reranker.time.sleep", return_value=None):
                s = RerankerService()
                ranked = s.rerank(query="test", documents=docs)

        assert len(ranked) == 1
        assert ranked[0]["score"] == 0.0

    def test_none_output_results_fallback(self):
        docs = ["A"]
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.output = None

        with mock.patch("agent.reranker.TextReRank.call", return_value=mock_response):
            s = RerankerService()
            ranked = s.rerank(query="test", documents=docs)

        assert len(ranked) == 1
        assert ranked[0]["score"] == 0.0


class TestRerankerAsync:
    """异步 rerank 测试。"""

    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        monkeypatch.setenv("APP_TOKEN", "sk-test")

    @pytest.mark.asyncio
    async def test_arerank_returns_same_as_sync(self):
        docs = ["A", "B", "C"]
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.output.results = [
            _make_result(2, 0.9),
            _make_result(0, 0.7),
            _make_result(1, 0.3),
        ]

        with mock.patch("agent.reranker.TextReRank.call", return_value=mock_response):
            s = RerankerService()
            ranked = await s.arerank(query="test", documents=docs)

        assert len(ranked) == 3
        assert ranked[0]["index"] == 2
        assert ranked[1]["index"] == 0
        assert ranked[2]["index"] == 1


class TestGetReranker:
    """全局单例测试。"""

    def test_singleton_same_instance(self, monkeypatch):
        monkeypatch.setenv("APP_TOKEN", "sk-test")
        import agent.reranker as mod
        mod._reranker = None  # reset

        a = get_reranker()
        b = get_reranker()
        assert a is b

    def test_singleton_resets_with_new_import(self, monkeypatch):
        monkeypatch.setenv("APP_TOKEN", "sk-test")
        import agent.reranker as mod
        mod._reranker = None
        r = get_reranker()
        assert isinstance(r, RerankerService)


# ── helpers ─────────────────────────────────────────────────────────────

def _make_result(index: int, score: float):
    """构造模拟的 ReRankResult。"""
    r = mock.Mock()
    r.index = index
    r.relevance_score = score
    r.document = {}
    return r
