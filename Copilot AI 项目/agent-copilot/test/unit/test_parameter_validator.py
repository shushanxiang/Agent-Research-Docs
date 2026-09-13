"""测试代码层参数校验（覆盖 P0-05）"""

import pytest
from conftest import make_param, make_tool


class TestParameterValidator:
    """参数校验器测试"""

    @classmethod
    def setup_class(cls):
        from param_extraction.parameter_validator import ParameterValidator
        cls.Validator = ParameterValidator

    def test_negative_quantity(self):
        """负值检测 — 面试官地平线 Q1 的核心场景"""
        tool = make_tool("test_tool", [make_param("quantity", "int32")])
        errors = self.Validator.validate(tool, {"quantity": -10})
        assert len(errors) > 0
        assert any("负数" in e or "不能为负数" in e for e in errors)

    def test_empty_string(self):
        """空字符串参数应被拒绝"""
        tool = make_tool("test_tool", [make_param("productId", "string")])
        errors = self.Validator.validate(tool, {"productId": ""})
        assert len(errors) > 0
        assert any("空字符串" in e for e in errors)

    def test_zero_is_valid(self):
        """0 不应被判定为非法"""
        tool = make_tool("test_tool", [make_param("quantity", "int32")])
        errors = self.Validator.validate(tool, {"quantity": 0})
        assert len(errors) == 0

    def test_positive_value_passes(self):
        """正常正值应通过"""
        tool = make_tool("test_tool", [
            make_param("quantity", "int32"),
            make_param("price", "double"),
        ])
        errors = self.Validator.validate(tool, {"quantity": 10, "price": 99.9})
        assert len(errors) == 0

    def test_invalid_date_format(self):
        """日期格式校验 — 千问不转时间戳的场景"""
        tool = make_tool("test_tool", [make_param("startDate", "date-time")])
        errors = self.Validator.validate(tool, {"startDate": "2025年12月1日"})
        assert len(errors) > 0
        assert any("日期格式" in e for e in errors)

    def test_valid_date_iso(self):
        """ISO 8601 日期应通过"""
        tool = make_tool("test_tool", [make_param("startDate", "date-time")])
        errors = self.Validator.validate(tool, {"startDate": "2025-08-12T13:58:04Z"})
        assert len(errors) == 0

    def test_enum_value_valid(self):
        """合法枚举值应通过"""
        tool = make_tool("test_tool", [make_param("status", "string", enum=["已完成", "待发货"])])
        errors = self.Validator.validate(tool, {"status": "已完成"})
        assert len(errors) == 0

    def test_enum_value_invalid(self):
        """非法枚举值应被拒绝"""
        tool = make_tool("test_tool", [make_param("status", "string", enum=["已完成", "待发货"])])
        errors = self.Validator.validate(tool, {"status": "不存在状态"})
        assert len(errors) > 0
        assert any("不在允许范围" in e for e in errors)

    def test_string_length_limit(self):
        """超长字符串检测（可能注入攻击）"""
        tool = make_tool("test_tool", [make_param("description", "string")])
        errors = self.Validator.validate(tool, {"description": "x" * 15000})
        assert len(errors) > 0
        assert any("过长" in e or "注入" in e for e in errors)

    def test_string_under_limit_passes(self):
        """长度正常的字符串应通过"""
        tool = make_tool("test_tool", [make_param("description", "string")])
        errors = self.Validator.validate(tool, {"description": "正常描述文字"})
        assert len(errors) == 0

    def test_missing_param_skipped(self):
        """未提供的参数不校验（由 validate_params 处理缺失）"""
        tool = make_tool("test_tool", [
            make_param("quantity", "int32"),
            make_param("price", "double", required=True),
        ])
        errors = self.Validator.validate(tool, {"quantity": 10})
        assert len(errors) == 0  # price 未提供，跳过

    def test_heuristic_keyword_match(self):
        """启发式关键词匹配：参数名含关键词即应用规则"""
        tool = make_tool("test_tool", [make_param("orderCount", "int32")])
        errors = self.Validator.validate(tool, {"orderCount": -5})
        assert len(errors) > 0
        assert any("数" in e or "负数" in e for e in errors)

    def test_price_zero_valid(self):
        """价格为 0 应通过"""
        tool = make_tool("test_tool", [make_param("price", "double")])
        errors = self.Validator.validate(tool, {"price": 0.0})
        assert len(errors) == 0

    def test_page_size_positive(self):
        """分页参数必须 > 0"""
        tool = make_tool("test_tool", [make_param("pageSize", "int32")])
        errors = self.Validator.validate(tool, {"pageSize": 0})
        assert len(errors) > 0

    def test_multiple_errors(self):
        """多个参数同时校验失败应报告所有错误"""
        tool = make_tool("test_tool", [
            make_param("quantity", "int32"),
            make_param("productName", "string"),
        ])
        errors = self.Validator.validate(tool, {"quantity": -1, "productName": ""})
        assert len(errors) == 2
