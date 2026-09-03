"""
跨数据库类型兼容模块
====================
统一封装 UUID / JSONB 类型，自动适配当前数据库方言：

  - PostgreSQL: 使用原生 UUID / JSONB
  - SQLite:     使用 String(36) / JSON，并自动将 uuid.UUID 对象转字符串

用法：
  from app.core.types import UUIDType, JSONType
  id = Column(UUIDType, primary_key=True)
  data = Column(JSONType, default=list)
"""

import json
import uuid

from sqlalchemy import String, Text, TypeDecorator, types
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID


def _is_sqlite():
    from app.core.config import settings
    return settings.DATABASE_URL.startswith("sqlite")


_IS_SQLITE = _is_sqlite()


class _UUIDString(TypeDecorator):
    """
    SQLite 兼容的 UUID 类型：
    - 存储: uuid.UUID → 字符串 (36字符)
    - 读取: 字符串 → uuid.UUID
    """
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value))
        except (ValueError, AttributeError):
            return value


class _JSONText(TypeDecorator):
    """
    SQLite 兼容的 JSON 类型（Text 存储，序列化/反序列化）：
    - 存储: dict/list → JSON 字符串
    - 读取: JSON 字符串 → dict/list
    """
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value


# ── 导出类型 ──
UUIDType = _UUIDString if _IS_SQLITE else PG_UUID(as_uuid=True)
JSONType = _JSONText if _IS_SQLITE else JSONB
