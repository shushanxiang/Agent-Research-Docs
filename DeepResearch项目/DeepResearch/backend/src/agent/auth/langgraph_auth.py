"""LangGraph 平台级别的认证函数.

在 langgraph.json 中通过 "auth" 字段引用此模块，对所有 LangGraph
Runtime 原生端点（/threads、/runs、/assistants）进行认证拦截。
"""
from __future__ import annotations

from langgraph_sdk.auth import Auth

from agent.auth.session import get_session

auth = Auth()


@auth.authenticate
async def authenticate_user(request):
    """LangGraph 平台认证入口.

    从请求 Cookie 中读取 session_id，校验 Redis 会话。
    校验成功返回用户身份信息（写入 LangGraph 审计日志），
    校验失败抛出异常（LangGraph 返回 401）。

    Args:
        request: Starlette Request 对象

    Returns:
        dict: 用户身份信息 {"identity": username, ...}

    Raises:
        Exception: 未登录或会话已过期
    """
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise Exception("未登录，请先登录")

    session_data = await get_session(session_id)
    if session_data is None:
        raise Exception("会话已过期，请重新登录")

    return {
        "identity": session_data["username"],
        "user_id": session_data["user_id"],
    }
