"""
会话模型
========
User / ChatSession — 用户与问答会话（支持规范问答/图集问答）
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, CheckConstraint, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.types import UUIDType, JSONType


class User(Base):
    __tablename__ = "users"

    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    role = Column(String(50), default="viewer")
    org_id = Column(UUIDType, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id = Column(UUIDType, ForeignKey("users.id"))
    title = Column(String(200))
    session_type = Column(String(50))
    messages = Column(JSONType, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "session_type IN ('规范问答','图集问答')",
            name="ck_session_type",
        ),
    )
