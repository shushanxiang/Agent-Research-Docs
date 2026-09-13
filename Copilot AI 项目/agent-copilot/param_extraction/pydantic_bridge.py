"""Pydantic 运行时模型桥接

从 Tool 的 Parameter 列表动态构造 Pydantic model，提供类型校验和自动类型转换。
作为参数提取链路中的第二道防线（第一道是 LLM Prompt 约束）。

"""

from typing import Any, Optional

from pydantic import ValidationError, create_model

# 字段类型映射（Parameter.type → Python 类型）
TYPE_MAP: dict[str, type] = {
    "string": str,
    "int32": int,
    "int64": int,
    "double": float,
    "float": float,
    "boolean": bool,
    "array": list,
}


def build_pydantic_model(params: list) -> type:
    """从 Parameter 列表动态构造 Pydantic model。

    所有字段均为 Optional，必填检查由调用方手动完成。
    Pydantic 层只负责类型校验和自动类型转换。

    Args:
        params: tool.request_body，即 List[Parameter]（MongoEngine EmbeddedDocument）

    Returns:
        一个 Pydantic model 类，可用于校验和类型转换
    """
    fields: dict[str, tuple] = {}
    for p in params:
        py_type = TYPE_MAP.get(p.type, str)
        # 统一用 Optional，required 检查由 validate_params 手动处理
        fields[p.name] = (Optional[py_type], None)
    return create_model("DynamicToolParam", **fields)
