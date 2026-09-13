# mypy: disable - error - code = "no-untyped-def,misc"
import pathlib
import json
import asyncio
import traceback
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger
from agent.logger import setup_logger, log_request_details
from agent.configuration import Configuration, load_available_models_from_env
from agent.task_queue import enqueue_task, start_worker, read_task_events
from agent.auth.middleware import AuthMiddleware
from agent.auth.routes import router as auth_router

# ── 应用 lifespan（管理后台任务启动/关闭）───────────────────────────


@asynccontextmanager
async def _app_lifespan(app: FastAPI):
    """应用级 lifespan：管理后台任务的启动和关闭."""
    try:
        asyncio.create_task(start_worker())
    except Exception as exc:
        logger.warning(f"[TaskQueue] worker 启动失败 ({type(exc).__name__}): {exc}")
    yield
    # 关闭数据库引擎
    try:
        from agent.db.engine import close_engine
        await close_engine()
    except Exception as exc:
        logger.warning(f"[数据库] 关闭引擎时出错 ({type(exc).__name__}): {exc}")


app = FastAPI(docs_url=None, redoc_url=None, lifespan=_app_lifespan)
setup_logger()

# ── 认证中间件（最先添加 = 最外层，拦截非登录请求）─────────────
app.add_middleware(AuthMiddleware)

# ── 注册认证路由 ───────────────────────────────────────────────────
app.include_router(auth_router)

# ── API 路由 ─────────────────────────────────────────────────────────

# 添加获取模型列表的API端点
@app.get("/api/models")
async def get_available_models():
    """获取可用的LLM模型列表"""
    try:
        # 直接从环境变量加载模型列表
        models = load_available_models_from_env()
        models_data = [
            {
                "model_id": model.model_id,
                "display_name": model.display_name,
                "icon": model.icon,
                "icon_color": model.icon_color
            }
            for model in models
        ]
        logger.info(f"返回模型列表: {models_data}")
        return JSONResponse(content={"models": models_data})
    except ValueError as e:
        # 配置解析错误（如 AVAILABLE_MODELS JSON 格式错误）
        logger.error(f"模型配置解析失败 (ValueError): {e}")
        return JSONResponse(
            content={"error": "模型配置格式错误，请检查 AVAILABLE_MODELS 环境变量", "details": str(e)},
            status_code=500
        )
    except Exception as e:
        # 未知异常 — 记录完整 traceback 用于排查
        logger.error(f"获取模型列表失败 ({type(e).__name__}): {e}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            content={"error": "获取模型列表失败", "details": str(e)},
            status_code=500
        )

# 添加请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    try:
        # 记录请求基本信息
        logger.info(f"收到用户请求：{request.method} {request.url}")

        # 如果是POST请求且有body，记录详细信息
        if request.method in ["POST", "PUT", "PATCH"]:
            body = await request.body()
            if body:
                try:
                    body_data = json.loads(body.decode())
                    log_request_details(body_data)
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.debug(
                        f"无法解析请求体为JSON ({type(e).__name__}): "
                        f"{body[:200]!r}"
                    )
                    log_request_details(body.decode())
    except Exception as e:
        # 日志记录本身的错误不应影响请求处理
        logger.error(
            f"记录请求日志时出错 ({type(e).__name__}): {e}\n"
            f"{traceback.format_exc()}"
        )

    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error(
            f"处理请求时出错 ({type(e).__name__}): {e}\n"
            f"请求: {request.method} {request.url}\n"
            f"{traceback.format_exc()}"
        )
        raise


# ── 异步研究端点（任务队列 + SSE）────────────────────────────────────

@app.post("/api/research")
async def submit_research(request: Request):
    """提交研究任务，立即返回 task_id 和 SSE 流地址.

    请求体示例：
    {
        "messages": [{"type": "human", "content": "分析AI芯片市场趋势"}],
        "initial_search_query_count": 3,
        "max_research_loops": 3,
        "reasoning_model": "qwen-plus-latest"
    }
    """
    user_id: int = getattr(request.state, "user_id", 0)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            content={"error": "请求体必须是 JSON 格式"},
            status_code=400,
        )

    try:
        task_id = await enqueue_task(
            messages=body.get("messages", []),
            initial_search_query_count=body.get("initial_search_query_count", 2),
            max_research_loops=body.get("max_research_loops", 2),
            reasoning_model=body.get("reasoning_model", ""),
            plan_status=body.get("plan_status", "unconfirmed"),
            plan=body.get("plan", ""),
            task_id=body.get("task_id", "")  # 前端回传则复用，否则后端生成新 UUID
        )
    except Exception as exc:
        logger.error(f"[TaskQueue] 任务入队失败 ({type(exc).__name__}): {exc}")
        return JSONResponse(
            content={"error": f"任务提交失败: {exc}"},
            status_code=503,
        )

    # 建立用户与 task（thread）的关联
    try:
        from agent.db.engine import get_session_factory
        from agent.db.models import UserThread
        from sqlalchemy import select

        # 从用户输入中提取主题摘要作为 title（取第一条 human 消息 = 用户原始问题）
        messages = body.get("messages", [])
        title_text = ""
        for m in messages:
            if m.get("type") == "human" and m.get("content", "").strip():
                title_text = m["content"].strip()[:256]
                break

        async with get_session_factory()() as session:
            # 检查是否已存在（同一事务内先查后插）
            existing = await session.execute(
                select(UserThread).where(
                    UserThread.user_id == user_id,
                    UserThread.thread_id == task_id,
                )
            )
            if existing.scalar_one_or_none() is None:
                session.add(UserThread(
                    user_id=user_id,
                    thread_id=task_id,
                    title=title_text,
                ))
                await session.commit()
    except Exception as exc:
        logger.warning(f"[用户关联] 写入 user_threads 失败 ({type(exc).__name__}): {exc}")
        # 不影响任务提交的响应，关联可以后续补录

    return JSONResponse(content={
        "task_id": task_id,
        "stream_url": f"/api/research/{task_id}/stream",
    })


@app.get("/api/research/{task_id}/stream")
async def stream_research(task_id: str, request: Request):
    """SSE 端点：推送研究进度事件。

    客户端断开后可用 Last-Event-ID header 重连，不会丢失中间事件。
    """
    last_event_id = request.headers.get("Last-Event-ID", "0")

    async def event_generator():
        try:
            async for event_str in read_task_events(task_id, last_event_id):
                yield f"data: {event_str}\n\n"
        except Exception as exc:
            logger.warning(f"[TaskQueue] SSE 推送异常 ({type(exc).__name__}): {exc}")
            yield f"data: {{\"error\": \"{exc}\"}}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        },
    )
