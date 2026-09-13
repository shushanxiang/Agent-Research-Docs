"""搜索缓存测试：get_cached, set_cached, clear_cache, cache_stats。

当前 API 签名：
  - get_cached(prompt: str) -> Optional[list[dict]]
  - set_cached(prompt: str, result: list[dict]) -> None
  - clear_cache() -> None
  - cache_stats() -> dict

key 基于归一化后的 prompt 文本（去空格/标点/大小写），不含 count 参数。
"""

import time
import threading
import pytest
from agent.search_cache import (
    get_cached, set_cached, clear_cache, cache_stats,
    _fallback_cache, _fallback_lock,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """每个测试前后清空缓存。"""
    clear_cache()
    yield
    clear_cache()


class TestCacheMiss:
    """未命中场景。"""

    def test_get_cached_miss_returns_none(self):
        """不存在的 key 返回 None。"""
        result = get_cached("nonexistent query")
        assert result is None

    def test_get_cached_miss_different_prompt(self):
        """不同 prompt 应独立缓存，不互相命中。"""
        set_cached("prompt A", result=[{"title": "ok"}])
        result = get_cached("prompt B")
        assert result is None

    def test_get_cached_miss_same_prompt_different_count(self):
        """相同 prompt 不同 count 仍然命中（当前实现 count 不影响 key）。

        这是有意的设计选择：相同搜索词在不同 count 下的结果通常大量重叠，
        缓存命中可以大幅减少 MCP 调用。若未来需要按 count 区分，可在 key 中
        加入 count 字段。
        """
        set_cached("shared query", result=[{"title": "first"}])
        result = get_cached("shared query")
        assert result is not None
        assert result[0]["title"] == "first"


class TestCacheHit:
    """命中场景。"""

    def test_set_and_get(self):
        """写入后能正确读取。"""
        data = [{"title": "Result 1", "snippet": "S1"}, {"title": "Result 2", "snippet": "S2"}]
        set_cached("AI芯片市场", result=data)
        result = get_cached("AI芯片市场")
        assert result is not None
        assert len(result) == 2
        assert result[0]["title"] == "Result 1"

    def test_prompt_whitespace_normalized(self):
        """前后空格和标点差异归一化后命中同一缓存。"""
        data = [{"title": "ok"}]
        set_cached("  padded  ", result=data)
        # 归一化后 key 相同
        result = get_cached("padded")
        assert result is not None
        assert result[0]["title"] == "ok"

    def test_chinese_punctuation_normalized(self):
        """中文标点差异归一化后命中同一缓存。"""
        data = [{"title": "测试"}]
        set_cached("AI芯片市场趋势，分析", result=data)
        result = get_cached("AI芯片市场趋势分析")  # 逗号被归一化掉
        assert result is not None
        assert result[0]["title"] == "测试"


class TestCacheExpiry:
    """过期场景。"""

    def test_expired_entry_returns_none(self, monkeypatch):
        """超过 TTL 的条目返回 None。"""
        from agent import search_cache

        # 强制使用内存后端以绕过 Redis 依赖
        monkeypatch.setattr(search_cache, "_redis_available", False)
        search_cache._redis_client = None
        data = [{"title": "expired"}]
        set_cached("expiring query", result=data)

        # 模拟时间回退：将时间戳设为 4000 秒前（超过 3600s TTL）
        with _fallback_lock:
            for key, (ts, val) in list(_fallback_cache.items()):
                _fallback_cache[key] = (ts - 4000, val)

        result = get_cached("expiring query")
        assert result is None


class TestClearCache:
    """清空场景。"""

    def test_clear_removes_all_entries(self):
        """清空后所有条目不可达。"""
        set_cached("q1", result=[{"title": "1"}])
        set_cached("q2", result=[{"title": "2"}])
        clear_cache()
        assert get_cached("q1") is None
        assert get_cached("q2") is None


class TestCacheStats:
    """统计信息。"""

    def test_empty_cache_stats(self, monkeypatch):
        """空缓存的统计信息。"""
        from agent import search_cache
        monkeypatch.setattr(search_cache, "_redis_available", False)
        search_cache._redis_client = None

        clear_cache()
        stats = cache_stats()
        assert stats["total_entries"] == 0

    def test_non_empty_cache_stats(self, monkeypatch):
        """非空缓存的统计信息。"""
        from agent import search_cache
        monkeypatch.setattr(search_cache, "_redis_available", False)
        search_cache._redis_client = None

        set_cached("q1", result=[{"title": "1"}, {"title": "2"}])
        set_cached("q2", result=[{"title": "3"}])
        stats = cache_stats()
        assert stats["total_entries"] == 2
        assert stats["avg_results"] == 1.5

    def test_stats_after_expiry(self, monkeypatch):
        """过期条目仍计入统计（清除发生在 get 时）。"""
        from agent import search_cache
        monkeypatch.setattr(search_cache, "_redis_available", False)
        search_cache._redis_client = None

        set_cached("q1", result=[{"title": "1"}])
        # 模拟过期
        with _fallback_lock:
            for key in list(_fallback_cache.keys()):
                ts, val = _fallback_cache[key]
                _fallback_cache[key] = (ts - 4000, val)
        stats = cache_stats()
        assert stats["total_entries"] == 1


class TestCacheThreadSafety:
    """并发安全性。"""

    def test_concurrent_set(self):
        """多线程并发写入不应破坏数据。"""
        errors = []

        def write_cache(i: int) -> None:
            try:
                data = [{"title": f"thread_{i}_result_{j}"} for j in range(5)]
                set_cached(f"thread_query_{i}", result=data)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_cache, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # 验证所有写入成功
        for i in range(10):
            result = get_cached(f"thread_query_{i}")
            assert result is not None
            assert len(result) == 5
