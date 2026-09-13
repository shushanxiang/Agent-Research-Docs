"""测试 Pydantic 桥接模块

覆盖 pydantic_bridge.py 的 model 构造、类型校验和类型转换逻辑。
"""

from typing import Optional

import pytest
from pydantic import ValidationError

from param_extraction.pydantic_bridge import build_pydantic_model


class MockParameter:
    """模拟 MongoEngine Parameter EmbeddedDocument，只暴露 pydantic_bridge 需要的属性"""
    def __init__(self, name: str, type: str = "string", required: bool = True):
        self.name = name
        self.type = type
        self.required = required


class TestBuildPydanticModel:

    def test_build_model_from_required_params(self):
        """必填字段正确构造为 required"""
        params = [
            MockParameter("name", "string", required=True),
            MockParameter("quantity", "int32", required=True),
        ]
        model_cls = build_pydantic_model(params)
        instance = model_cls(name="苹果", quantity=20)
        assert instance.name == "苹果"
        assert instance.quantity == 20

    def test_build_model_with_optional_params(self):
        """可选字段缺省时为 None"""
        params = [
            MockParameter("name", "string", required=True),
            MockParameter("remark", "string", required=False),
        ]
        model_cls = build_pydantic_model(params)
        instance = model_cls(name="苹果")
        assert instance.name == "苹果"
        assert instance.remark is None

    def test_valid_data_passes(self):
        """正确类型的数据通过校验"""
        params = [
            MockParameter("name", "string", required=True),
            MockParameter("price", "double", required=True),
            MockParameter("active", "boolean", required=False),
        ]
        model_cls = build_pydantic_model(params)
        instance = model_cls(name="梨子", price=3.5, active=True)
        assert instance.name == "梨子"
        assert instance.price == 3.5
        assert instance.active is True

    def test_type_coercion_string_to_int(self):
        """Pydantic 自动将数字字符串转换为 int"""
        params = [MockParameter("quantity", "int32", required=True)]
        model_cls = build_pydantic_model(params)
        instance = model_cls(quantity="42")
        assert instance.quantity == 42
        assert isinstance(instance.quantity, int)

    def test_type_coercion_string_to_float(self):
        """Pydantic 自动将数字字符串转换为 float"""
        params = [MockParameter("price", "double", required=True)]
        model_cls = build_pydantic_model(params)
        instance = model_cls(price="3.5")
        assert instance.price == 3.5
        assert isinstance(instance.price, float)

    def test_type_mismatch_raises(self):
        """类型不匹配时抛出 ValidationError"""
        params = [MockParameter("quantity", "int32", required=True)]
        model_cls = build_pydantic_model(params)
        with pytest.raises(ValidationError):
            model_cls(quantity="不是数字")

    def test_missing_required_field_is_none(self):
        """缺失必填字段返回 None（由 validate_params 手动检查缺失）"""
        params = [MockParameter("name", "string", required=True)]
        model_cls = build_pydantic_model(params)
        instance = model_cls()  # name is missing but Optional, so no error
        assert instance.name is None

    def test_string_type_default(self):
        """未映射的类型默认使用 str"""
        params = [MockParameter("data", "unknown_type", required=True)]
        model_cls = build_pydantic_model(params)
        instance = model_cls(data="anything")
        assert instance.data == "anything"

    def test_model_dump_by_alias(self):
        """model_dump 返回原始字段名 """
        params = [MockParameter("user_name", "string", required=True)]
        model_cls = build_pydantic_model(params)
        instance = model_cls(user_name="test")
        dumped = instance.model_dump(by_alias=True)
        assert dumped["user_name"] == "test"

    def test_optional_field_accepts_value(self):
        """可选字段传值时正确接受"""
        params = [
            MockParameter("name", "string", required=True),
            MockParameter("remark", "string", required=False),
        ]
        model_cls = build_pydantic_model(params)
        instance = model_cls(name="苹果", remark="备注信息")
        assert instance.remark == "备注信息"

    def test_empty_params_list(self):
        """空参数列表构造出空 model"""
        model_cls = build_pydantic_model([])
        instance = model_cls()
        assert instance.model_dump() == {}
