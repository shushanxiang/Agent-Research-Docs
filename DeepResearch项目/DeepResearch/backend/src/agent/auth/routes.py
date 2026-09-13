"""登录路由."""
from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy import select
import bcrypt as _bcrypt

from agent.db.engine import get_session_factory
from agent.db.models import User
from agent.auth.session import create_session, delete_session

router = APIRouter()


@router.post("/api/login")
async def login(request: Request, response: Response):
    """用户登录接口.

    请求体：{"username": "zhangsan", "password": "zhangsan"}
    成功：设置 session_id Cookie，返回用户信息
    失败：返回 401
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            content={"error": "请求体必须是 JSON 格式"},
            status_code=400,
        )

    username = body.get("username", "").strip()
    password = body.get("password", "")

    if not username or not password:
        return JSONResponse(
            content={"error": "用户名和密码不能为空"},
            status_code=400,
        )

    # 从数据库查找用户
    async with get_session_factory()() as session:
        result = await session.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()

    if user is None:
        logger.warning(f"[Auth] 登录失败：用户 {username} 不存在")
        return JSONResponse(
            content={"error": "用户名或密码错误"},
            status_code=401,
        )

    # 验证密码
    try:
        password_ok = _bcrypt.checkpw(
            password.encode("utf-8"),
            user.password.encode("utf-8"),
        )
    except Exception:
        password_ok = False

    if not password_ok:
        logger.warning(f"[Auth] 登录失败：用户 {username} 密码错误")
        return JSONResponse(
            content={"error": "用户名或密码错误"},
            status_code=401,
        )

    # 创建 Redis 会话
    session_id = await create_session(user.id, user.username)

    logger.info(f"[Auth] 用户 {username} 登录成功")

    resp = JSONResponse(content={
        "username": user.username,
        "user_id": user.id,
    })
    # 设置 Cookie（HttpOnly 防 XSS，SameSite Lax 防 CSRF）
    resp.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=86400,  # 24 小时
        path="/",
    )
    return resp


@router.post("/api/logout")
async def logout(request: Request, response: Response):
    """用户登出接口：删除 Redis 会话并清除 Cookie."""
    session_id = request.cookies.get("session_id")
    if session_id:
        await delete_session(session_id)

    resp = JSONResponse(content={"message": "已登出"})
    resp.delete_cookie("session_id", path="/")
    return resp


@router.get("/api/whoami")
async def whoami(request: Request):
    """获取当前登录用户信息（用于前端判断登录状态）."""
    session_id = request.cookies.get("session_id")
    if not session_id:
        return JSONResponse(content={"logged_in": False})

    from agent.auth.session import get_session
    session_data = await get_session(session_id)
    if session_data is None:
        return JSONResponse(content={"logged_in": False})

    return JSONResponse(content={
        "logged_in": True,
        "username": session_data["username"],
        "user_id": int(session_data["user_id"]),
    })
