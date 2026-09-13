"""Tests for task_queue — Redis Streams 任务队列模块.

测试覆盖：
  - 导入验证（无导入错误）
  - enqueue_task 入队逻辑（mock Redis）
  - read_task_events 事件读取（mock Redis）
  - 终止事件检测（error / finalize_answer / task_paused）
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════
# 导入验证
# ═══════════════════════════════════════════════════════════════════════

class TestTaskQueueImport:
    def test_import_succeeds(self):
        """验证 task_queue 模块可以正常导入。"""
        from agent.task_queue import (
            enqueue_task,
            start_worker,
            read_task_events,
            TASK_STREAM,
            EVENT_STREAM_PREFIX,
            CONSUMER_GROUP,
        )
        assert TASK_STREAM == "research:tasks"
        assert EVENT_STREAM_PREFIX == "research:events"
        assert CONSUMER_GROUP == "research-workers"


# ═══════════════════════════════════════════════════════════════════════
# enqueue_task 测试
# ═══════════════════════════════════════════════════════════════════════

class TestEnqueueTask:
    @pytest.mark.asyncio
    async def test_enqueue_returns_task_id(self):
        """验证入队返回有效的 task_id。"""
        from agent.task_queue import enqueue_task, _get_redis

        mock_redis = MagicMock()
        mock_redis.xadd = AsyncMock()

        with patch("agent.task_queue._get_redis", return_value=mock_redis):
            task_id = await enqueue_task(
                messages=[{"type": "human", "content": "测试"}],
                initial_search_query_count=2,
                max_research_loops=2,
                reasoning_model="test-model",
            )

        # 验证返回的是有效的 UUID 格式
        assert isinstance(task_id, str)
        assert len(task_id) == 36  # UUID 标准长度

    @pytest.mark.asyncio
    async def test_enqueue_calls_xadd_with_payload(self):
        """验证入队时正确调用 Redis XADD。"""
        from agent.task_queue import enqueue_task, _get_redis, TASK_STREAM

        mock_redis = MagicMock()
        mock_redis.xadd = AsyncMock()

        with patch("agent.task_queue._get_redis", return_value=mock_redis):
            await enqueue_task(
                messages=[{"type": "human", "content": "分析AI芯片"}],
                initial_search_query_count=3,
                max_research_loops=5,
                reasoning_model="qwen-test",
            )

        # 验证 xadd 被调用
        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        # xadd(stream_name, {"task": payload}, maxlen=...)
        # call_args = ((stream_name, {"task": payload}), {"maxlen": ...})
        assert call_args[0][0] == TASK_STREAM
        payload = json.loads(call_args[0][1]["task"])
        assert payload["initial_search_query_count"] == 3
        assert payload["max_research_loops"] == 5
        assert payload["reasoning_model"] == "qwen-test"
        assert "task_id" in payload


# ═══════════════════════════════════════════════════════════════════════
# read_task_events 测试
# ═══════════════════════════════════════════════════════════════════════

class TestReadTaskEvents:
    @pytest.mark.asyncio
    async def test_read_events_yields_from_stream(self):
        """验证从 Stream 读取事件并 yield。"""
        from agent.task_queue import read_task_events, _get_redis

        mock_redis = MagicMock()
        # 模拟一次 xread 返回一个事件
        mock_redis.xread = AsyncMock(return_value=[
            [
                b"research:events:test-id",
                [
                    (b"1234567890-0", {"event": json.dumps({"generate_plan": {"plan": "test plan"}})}),
                ],
            ]
        ])

        with patch("agent.task_queue._get_redis", return_value=mock_redis):
            gen = read_task_events("test-id")
            results = []
            async for event_str in gen:
                results.append(event_str)
                break  # 只取第一个事件

        assert len(results) == 1
        event = json.loads(results[0])
        assert "generate_plan" in event

    @pytest.mark.asyncio
    async def test_error_event_stops_generator(self):
        """验证 error 事件会终止 generator。"""
        from agent.task_queue import read_task_events, _get_redis

        mock_redis = MagicMock()
        mock_redis.xread = AsyncMock(return_value=[
            [
                b"research:events:test-id",
                [
                    (b"1234567890-0", {"event": json.dumps({"error": "测试错误"})}),
                ],
            ]
        ])

        with patch("agent.task_queue._get_redis", return_value=mock_redis):
            gen = read_task_events("test-id")
            results = []
            async for event_str in gen:
                results.append(event_str)

        assert len(results) == 1
        event = json.loads(results[0])
        assert event["error"] == "测试错误"

    @pytest.mark.asyncio
    async def test_finalize_answer_stops_generator(self):
        """验证 finalize_answer 事件会终止 generator。"""
        from agent.task_queue import read_task_events, _get_redis

        mock_redis = MagicMock()
        mock_redis.xread = AsyncMock(return_value=[
            [
                b"research:events:test-id",
                [
                    (b"1234567890-0", {"event": json.dumps({"finalize_answer": {"messages": []}})}),
                ],
            ]
        ])

        with patch("agent.task_queue._get_redis", return_value=mock_redis):
            gen = read_task_events("test-id")
            results = []
            async for event_str in gen:
                results.append(event_str)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_task_paused_stops_generator(self):
        """验证 task_paused 事件会终止 generator。"""
        from agent.task_queue import read_task_events, _get_redis

        mock_redis = MagicMock()
        mock_redis.xread = AsyncMock(return_value=[
            [
                b"research:events:test-id",
                [
                    (b"1234567890-0", {"event": json.dumps({"task_paused": True})}),
                ],
            ]
        ])

        with patch("agent.task_queue._get_redis", return_value=mock_redis):
            gen = read_task_events("test-id")
            results = []
            async for event_str in gen:
                results.append(event_str)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_non_terminal_events_continue(self):
        """验证非终止事件不会停止 generator（但测试中我们手动 break）。"""
        from agent.task_queue import read_task_events, _get_redis

        call_count = [0]
        mock_redis = MagicMock()

        async def mock_xread(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return [
                    [
                        b"research:events:test-id",
                        [(b"1234567890-0", {"event": json.dumps({"reflection": {}})})],
                    ]
                ]
            elif call_count[0] == 2:
                # 第二次调用时返回终止事件
                return [
                    [
                        b"research:events:test-id",
                        [(b"1234567890-1", {"event": json.dumps({"finalize_answer": {}})})],
                    ]
                ]
            return None

        mock_redis.xread = mock_xread

        with patch("agent.task_queue._get_redis", return_value=mock_redis):
            gen = read_task_events("test-id")
            results = []
            async for event_str in gen:
                results.append(event_str)

        # 应该收到两个事件：reflection + finalize_answer
        assert len(results) == 2
