"""基于 Redis Streams 的任务队列和事件流。

职责：
  - 任务入队：XADD research:tasks
  - 后台消费：XREADGROUP + 执行 LangGraph 图 + XACK
  - 事件发布：XADD research:events:{task_id}
  - SSE 读取：XREAD research:events:{task_id}

整个模块在 FastAPI 进程内以 asyncio 协程运行，无需独立 Worker 进程。
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid

import redis.asyncio as redis
from langchain_core.messages import HumanMessage, AIMessage
from loguru import logger

from agent.graph import build_graph
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
TASK_STREAM = "research:tasks"
EVENT_STREAM_PREFIX = "research:events"
CONSUMER_GROUP = "research-workers"
# 单个任务的事件流最大保留条数，防止无限增长
EVENT_STREAM_MAXLEN = 500
# XREAD 阻塞超时（毫秒），避免空轮询
STREAM_BLOCK_MS = 5000

# ── 子图内部节点名 → 前端事件名映射 ──────────────────────────────
# 重构为子图架构后，graph.astream() 需启用 subgraphs=True 才能获取子图内部事件。
# 子图内部节点名与前端约定的扁平事件名不一致，此处做翻译。
_SUBGRAPH_EVENT_MAP = {
    "generate_queries": "generate_query",
    "web_search": "web_research",
    "critique": "reflection",
}

_redis: redis.Redis | None = None
_persistent_graph = None  # 延迟初始化，带 Redis checkpoint 持久化


async def _get_redis() -> redis.Redis:
    """延迟获取 Redis 连接（复用同一个连接池）."""
    global _redis
    if _redis is None:
        _redis = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis


async def _get_graph():
    """获取带 Redis 持久化的编译图（延迟初始化 + 单例）."""
    global _persistent_graph
    if _persistent_graph is None:
        checkpointer = AsyncRedisSaver(
            REDIS_URL,
            ttl={"default_ttl": 60 * 24 * 7, "refresh_on_read": True},
        )
        await checkpointer.asetup()
        _persistent_graph = build_graph(checkpointer=checkpointer)
        logger.info("[TaskQueue] 已创建 AsyncRedisSaver 持久化图（TTL=7天）")
    return _persistent_graph


# ═══════════════════════════════════════════════════════════════════════
# 任务入队
# ═══════════════════════════════════════════════════════════════════════

async def enqueue_task(
    messages: list[dict],
    initial_search_query_count: int,
    max_research_loops: int,
    reasoning_model: str,
    plan_status: str = "unconfirmed",
    plan: str = "",
    task_id: str = "",
) -> str:
    """将研究任务写入 Redis Stream，返回 task_id。

    调用方（POST /api/research）拿到 task_id 后立即返回给前端。
    如果传入 task_id 则复用，否则生成新的 UUID。
    """
    r = await _get_redis()
    if not task_id:
        task_id = str(uuid.uuid4())
    task_payload = json.dumps({
        "task_id": task_id,
        "messages": messages,
        "initial_search_query_count": initial_search_query_count,
        "max_research_loops": max_research_loops,
        "reasoning_model": reasoning_model,
        "plan_status": plan_status,
        "plan": plan,
    })
    await r.xadd(TASK_STREAM, {"task": task_payload}, maxlen=1000)
    logger.info(f"[TaskQueue] 任务已入队 task_id={task_id[:8]}...")
    return task_id


# ═══════════════════════════════════════════════════════════════════════
# 后台消费协程（FastAPI startup 时启动）
# ═══════════════════════════════════════════════════════════════════════

async def start_worker() -> None:
    """启动后台消费协程，不阻塞 HTTP 请求处理。

    调用方式（在 app.py 的 startup 事件中）：
        asyncio.create_task(start_worker())
    """
    r = await _get_redis()
    await _ensure_consumer_group(r)
    logger.info("[TaskQueue] worker 协程已启动，等待任务...")
    while True:
        try:
            await _process_one_task(r)
        except asyncio.CancelledError:
            logger.info("[TaskQueue] worker 协程被取消")
            break
        except Exception as exc:
            logger.error(f"[TaskQueue] worker 异常 ({type(exc).__name__}): {exc}")
            await asyncio.sleep(1)  # 短暂等待后继续


async def _ensure_consumer_group(r: redis.Redis) -> None:
    """创建 Consumer Group（如果不存在）."""
    try:
        await r.xgroup_create(TASK_STREAM, CONSUMER_GROUP, id="0", mkstream=True)
        logger.info(f"[TaskQueue] Consumer Group '{CONSUMER_GROUP}' 已创建")
    except redis.ResponseError as e:
        if "BUSYGROUP" in str(e):
            logger.debug(f"[TaskQueue] Consumer Group 已存在，跳过创建")
        else:
            raise


async def _process_one_task(r: redis.Redis) -> None:
    """消费并执行一个任务."""
    # 从 Consumer Group 读取一条待处理任务
    result = await r.xreadgroup(
        CONSUMER_GROUP,
        "worker-1",  # 消费者名称（多实例时每实例一个唯一名）
        {TASK_STREAM: ">"},
        block=STREAM_BLOCK_MS,
        count=1,
    )
    if not result:
        return  # 超时，没有任务

    stream_name, messages = result[0]
    redis_msg_id, payload = messages[0]
    task = json.loads(payload["task"])
    task_id = task["task_id"]

    logger.info(f"[TaskQueue] 开始执行任务 task_id={task_id[:8]}...")

    try:
        # 重建消息列表（保留完整历史及原始 ID，确保 add_messages 按 ID 正确去重）
        messages = [
            HumanMessage(content=m["content"], id=m.get("id")) if m.get("type") == "human"
            else AIMessage(content=m["content"], id=m.get("id")) if m.get("type") == "ai"
            else None
            for m in task["messages"]
        ]
        messages = [m for m in messages if m is not None]

        # 这个函数将大模型流式输出的token借助Redis也流式输出到前端页面（供节点内 Agent 使用）
        async def emit_token(text: str, node: str) -> None:
            """将 LLM token 推送到 Redis 事件流."""
            try:
                event_json = json.dumps(
                    {"token": {"text": text, "node": node}},
                    ensure_ascii=False,
                )
                await r.xadd(
                    f"{EVENT_STREAM_PREFIX}:{task_id}",
                    {"event": event_json},
                    maxlen=EVENT_STREAM_MAXLEN,
                )
            except Exception as exc:
                logger.warning(f"[TaskQueue] token事件发送失败 node={node}: {exc}")

        config = {
            "configurable": {
                "thread_id": task_id,  # 将 task_id 作为 LangGraph 的 checkpoint thread_id
                "initial_search_query_count": task["initial_search_query_count"],
                "max_research_loops": task["max_research_loops"],
                "reasoning_model": task["reasoning_model"],
                "_emit_token": emit_token,
            }
        }

        # 图初始状态（支持 plan 确认后的 resume 场景）
        initial_state: dict = {
            "messages": messages,
            "plan_status": task.get("plan_status", "unconfirmed"),
            "plan": task.get("plan", ""),
        }

        # 执行图（Checkpointer可绑定 Redis，通过 thread_id 实现会话隔离）
        # subgraphs=True: 穿透子图边界，获取内部节点事件
        # 事件格式: (namespace, {node_name: node_output})
        # event = (("research:abc123",), {"generate_queries": {...}})
        #         └──── namespace ────┘  └──────── data ──────────┘
        #   - 父图节点:  namespace = (),     data = {"generate_plan": {...}}
        #   - 子图内部:  namespace = ("research:<id>",), data = {"generate_queries": {...}}
        final_answer_event = None
        persistent_graph = await _get_graph()
        async for event in persistent_graph.astream(initial_state, config, subgraphs=True):
            # ── 解析 subgraphs=True 的 2 元组格式 ─────────────────────
            #避免处理非节点事件，如：子图进入/退出时的边界事件、LangGraph调度层面的内部生命周期事件
            if not isinstance(event, tuple) or len(event) != 2:
                continue

            namespace: tuple = event[0]
            data: dict = event[1]

            if not isinstance(data, dict) or not data:
                continue

            # 从 data 中提取原始节点名和节点输出
            node_name = list(data.keys())[0]
            node_output = data[node_name]

            # 跳过 LangGraph 内部事件
            if not node_name or str(node_name).startswith("__"):
                continue

            # ── 事件名翻译：子图内部节点 → 前端扁平事件名 ────────────
            is_subgraph = len(namespace) > 0
            frontend_event_name = (
                _SUBGRAPH_EVENT_MAP.get(node_name, node_name)
                if is_subgraph
                else node_name
            )
            translated_event = {frontend_event_name: node_output}

            # 写入 Redis 事件流（前端根据事件名更新 UI，如气泡的显示，页面文本的合并等等或关闭SSE连接）
            event_json = json.dumps(translated_event, default=str, ensure_ascii=False)
            await r.xadd(
                f"{EVENT_STREAM_PREFIX}:{task_id}",
                {"event": event_json},
                maxlen=EVENT_STREAM_MAXLEN,
            )

            # 如果是 writer 子图返回（包含最终报告），提取为 finalize_answer
            if frontend_event_name == "write" and isinstance(node_output, dict):
                if "messages" in node_output:
                    # 子图返回的消息列表可能包含历史消息（由 add_messages reducer 累积），
                    # 取最后一条 AI 消息作为最终报告内容
                    msgs = node_output["messages"]
                    ai_msgs = [m for m in msgs if getattr(m, "type", None) == "ai"]
                    final_msg = ai_msgs[-1] if ai_msgs else (msgs[-1] if msgs else None)
                    if final_msg:
                        final_answer_event = {
                            "finalize_answer": {
                                "messages": [
                                    {"content": final_msg.content, "type": "ai"}
                                ]
                            }
                        }

        logger.info(f"[TaskQueue] 任务完成 task_id={task_id[:8]}...")

        # 判断是正常完成还是暂停在 Plan 确认
        if final_answer_event:
            # 图正常完成 → 发射 finalize_answer
            event_json = json.dumps(final_answer_event, default=str, ensure_ascii=False)
            await r.xadd(
                f"{EVENT_STREAM_PREFIX}:{task_id}",
                {"event": event_json},
                maxlen=EVENT_STREAM_MAXLEN,
            )
        else:
            # 图执行完毕但未生成最终答案 → 在 Plan 确认处暂停
            pause_json = json.dumps({"task_paused": True}, ensure_ascii=False)
            await r.xadd(
                f"{EVENT_STREAM_PREFIX}:{task_id}",
                {"event": pause_json},
                maxlen=EVENT_STREAM_MAXLEN,
            )

    except Exception as exc:
        logger.error(f"[TaskQueue] 任务失败 task_id={task_id[:8]}... ({type(exc).__name__}): {exc}")
        # 将错误作为事件推送给前端
        error_json = json.dumps({"error": str(exc)}, ensure_ascii=False)
        await r.xadd(
            f"{EVENT_STREAM_PREFIX}:{task_id}",
            {"event": error_json},
            maxlen=EVENT_STREAM_MAXLEN,
        )

    finally:
        # 确认消息已处理
        await r.xack(TASK_STREAM, CONSUMER_GROUP, redis_msg_id)
        # 清理事件流（设置过期，24 小时后自动删除）
        await r.expire(f"{EVENT_STREAM_PREFIX}:{task_id}", 86400)


# ═══════════════════════════════════════════════════════════════════════
# SSE 事件读取
# ═══════════════════════════════════════════════════════════════════════

async def read_task_events(task_id: str, last_event_id: str = "0"):
    """Generator: 从 Redis Stream 读取任务事件，用于 SSE 推送。

    支持断线重连：客户端通过 SSE 的 Last-Event-ID header 传入 last_event_id，
    服务端从该 ID 之后开始推送。
    """
    r = await _get_redis()
    stream_key = f"{EVENT_STREAM_PREFIX}:{task_id}"
    current_id = last_event_id

    while True:
        try:
            result = await r.xread(
                {stream_key: current_id},
                block=STREAM_BLOCK_MS,
                count=10,
            )
            if result:
                for _, messages in result:
                    for msg_id, data in messages:
                        event_str = data.get("event", "{}")
                        current_id = msg_id
                        yield event_str

                        # 检查是否为终止事件（错误 / finalize_answer / task_paused）
                        try:
                            event = json.loads(event_str)
                            if any(k in event for k in ("error", "finalize_answer", "task_paused")):
                                return  # 任务结束，关闭 SSE 连接
                        except json.JSONDecodeError:
                            pass

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning(f"[TaskQueue] SSE 读取异常 ({type(exc).__name__}): {exc}")
            await asyncio.sleep(1)
