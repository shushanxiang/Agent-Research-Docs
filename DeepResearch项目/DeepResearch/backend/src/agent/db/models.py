"""数据库表模型（纯 SQL 表定义，不含 ORM 关系）."""
from __future__ import annotations

from sqlalchemy import Column, Integer, String, DateTime, Text, func, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class User(Base):
    """用户表."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), nullable=False, unique=True, index=True)
    password = Column(String(256), nullable=False)  # bcrypt 哈希
    created_at = Column(DateTime, server_default=func.now())


class UserThread(Base):
    """用户与研究线程的关联表（应用层管理 user_id → thread_id 映射）."""
    __tablename__ = "user_threads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    thread_id = Column(String(128), nullable=False)
    title = Column(Text, nullable=True)  # 研究主题，用于前端展示历史记录
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "thread_id", name="uq_user_threads_user_thread"),
        {"sqlite_autoincrement": True},
    )
