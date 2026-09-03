"""
数据库连接管理
==============
异步 SQLAlchemy 引擎 + 会话工厂 + 生命周期管理。

支持 PostgreSQL (asyncpg)，开发环境可降级为 SQLite。
提供 FastAPI 依赖注入：get_db() 自动管理会话生命周期。
"""

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── 共享 ORM Base ──
# 所有 models 文件统一从此处导入，保证单一 registry
Base = declarative_base()

# ── 引擎（延迟创建）──
_engine = None
_async_session_factory = None


def _get_engine():
    """延迟创建引擎，避免导入时即连接数据库"""
    global _engine

    if _engine is not None:
        return _engine

    database_url = settings.DATABASE_URL
    is_sqlite = database_url.startswith("sqlite")
    connect_args = {}
    if is_sqlite:
        connect_args["check_same_thread"] = False

    _engine = create_async_engine(
        database_url,
        echo=settings.DEBUG,
        pool_size=10,
        max_overflow=20,
        # SQLite 不支持 pool_pre_ping
        pool_pre_ping=not is_sqlite,
        connect_args=connect_args,
    )
    return _engine


def _get_session_factory():
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 依赖注入：每次请求创建独立数据库会话，完成后自动关闭。

    用法:
        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """
    应用启动时初始化数据库：
    1. 创建所有 ORM 表（如不存在）
    2. 不执行数据迁移（生产环境请使用 Alembic）
    """
    # 延迟导入，避免循环依赖
    import app.models.document   # noqa: F401  注册模型
    import app.models.session    # noqa: F401

    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("[Database] 表结构初始化完成")


async def dispose_db():
    """应用关闭时释放数据库连接池"""
    global _engine, _async_session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None
        logger.info("[Database] 连接池已释放")
