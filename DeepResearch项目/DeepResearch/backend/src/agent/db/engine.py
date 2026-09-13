"""数据库连接引擎和会话管理."""
from __future__ import annotations

import os
from loguru import logger
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/deepresearch")

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


def _create_engine() -> AsyncEngine:
    """创建异步数据库引擎（带连接池配置）."""
    return create_async_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,  # 连接前检查可用性
        echo=False,
    )


def get_engine() -> AsyncEngine:
    """获取或创建全局引擎实例."""
    global _engine
    if _engine is None:
        _engine = _create_engine()
        logger.info("[数据库] 异步引擎已创建")
    return _engine


def get_session_factory() -> async_sessionmaker:
    """获取或创建会话工厂."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_session() -> AsyncSession:
    """获取一个新的数据库会话（调用方负责关闭）."""
    factory = get_session_factory()
    return factory()


async def close_engine() -> None:
    """关闭数据库引擎（应用退出时调用）."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("[数据库] 引擎已关闭")
