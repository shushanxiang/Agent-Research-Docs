"""Redis 会话管理.

会话数据:
    key:   session:{session_id} → hash {
        "user_id": str,
        "username": str,
        "last_active": iso8601,
    }
    ttl:   86400 秒（24 小时），每次访问续期
"""
from __future__ import annotations

import os
import secrets
import time
from datetime import datetime, timezone

import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SESSION_TTL = 86400  # 24 小时
SESSION_PREFIX = "session:"

_redis: redis.Redis | None = None


async def _get_session_redis() -> redis.Redis:
    """获取会话 Redis 连接（与 task_queue 共享同一 Redis）."""
    global _redis
    if _redis is None:
        _redis = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis


async def create_session(user_id: int, username: str) -> str:
    """创建新会话，返回 session_id."""
    session_id = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc).isoformat()
    r = await _get_session_redis()
    key = f"{SESSION_PREFIX}{session_id}"
    await r.hset(key, mapping={
        "user_id": str(user_id),
        "username": username,
        "last_active": now,
    })
    await r.expire(key, SESSION_TTL)
    return session_id


async def get_session(session_id: str) -> dict | None:
    """获取并续期会话，返回会话数据或 None."""
    if not session_id:
        return None
    r = await _get_session_redis()
    key = f"{SESSION_PREFIX}{session_id}"
    exists = await r.exists(key)
    if not exists:
        return None
    # 续期
    now = datetime.now(timezone.utc).isoformat()
    await r.hset(key, "last_active", now)
    await r.expire(key, SESSION_TTL)
    data = await r.hgetall(key)
    return data if data else None


async def delete_session(session_id: str) -> None:
    """删除会话（用户登出时调用）."""
    if not session_id:
        return
    r = await _get_session_redis()
    await r.delete(f"{SESSION_PREFIX}{session_id}")
