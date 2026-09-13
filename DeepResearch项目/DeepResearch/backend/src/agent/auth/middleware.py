"""认证中间件：拦截非登录请求，校验 Redis 会话.

白名单：/api/login 不做拦截（无需登录即可访问）.
"""
from __future__ import annotations

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

from agent.auth.session import get_session


# 不需要登录即可访问的路径
PUBLIC_PATHS = {
    "/api/login",
    "/api/whoami",
    "/api/logout",
    "/api/models",
}


class AuthMiddleware(BaseHTTPMiddleware):
    """统一认证中间件：从 Cookie 读取 session_id，校验 Redis 会话."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # 白名单路径跳过认证
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        # 从 Cookie 中读取 session_id
        session_id = request.cookies.get("session_id")

        if not session_id:
            return JSONResponse(
                content={"error": "未登录，请先登录"},
                status_code=401,
            )

        session_data = await get_session(session_id)
        if session_data is None:
            return JSONResponse(
                content={"error": "会话已过期，请重新登录"},
                status_code=401,
            )

        # 将会话信息注入到 request.state 供后续路由使用
        request.state.user_id = int(session_data["user_id"])
        request.state.username = session_data["username"]

        return await call_next(request)
