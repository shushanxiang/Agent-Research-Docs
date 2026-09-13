"""额外参数校验和提取测试 — 覆盖 validate_params 和 extraction_params 深层分支"""

import os, sys, pytest
from unittest.mock import MagicMock

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


class TestValidateParamsDeep:
    """validate_params 深层分支测试"""

    @classmethod
    def setup_class(cls):
        from param_extraction.param_extraction_hub import ParamExtractionHub
        cls.hub = ParamExtractionHub.__new__(ParamExtractionHub)
        cls.hub.LargeLanguageModel = MagicMock()
        cls.hub.PromptModelHub = MagicMock()
        cls.hub.model = "test"
        cls.hub.temperature = 0.01
        cls.hub.top_p = 0.01

    def test_missing_required_param(self):
        from conftest import make_tool, make_param
        tool = make_tool("test", [
            make_param("required_field", "string", required=True),
            make_param("optional_field", "string", required=False),
        ])
        _, missing = self.hub.validate_params(tool, {"optional_field": "value"})
        assert len(missing) == 1
        assert missing[0].name == "required_field"

    def test_empty_string_required(self):
        from conftest import make_tool, make_param
        tool = make_tool("test", [make_param("name", "string", required=True)])
        _, missing = self.hub.validate_params(tool, {"name": ""})
        assert len(missing) == 1

    def test_int_conversion_valid(self):
        from conftest import make_tool, make_param
        tool = make_tool("test", [make_param("id", "int64")])
        extraction = {"id": "42"}
        converted, missing = self.hub.validate_params(tool, extraction)
        assert len(missing) == 0
        assert isinstance(converted["id"], int)
        assert converted["id"] == 42

    def test_int_conversion_invalid(self):
        from conftest import make_tool, make_param
        tool = make_tool("test", [make_param("id", "int64", required=True)])
        extraction = {"id": "not a number"}
        with pytest.raises(Exception):
            converted, missing = self.hub.validate_params(tool, extraction)


    def test_double_conversion_valid(self):
        from conftest import make_tool, make_param
        tool = make_tool("test", [make_param("price", "double")])
        extraction = {"price": "99.99"}
        converted, missing = self.hub.validate_params(tool, extraction)
        assert len(missing) == 0
        assert isinstance(converted["price"], float)

    def test_double_conversion_invalid(self):
        from conftest import make_tool, make_param
        tool = make_tool("test", [make_param("price", "double", required=True)])
        extraction = {"price": "invalid_float"}
        with pytest.raises(Exception):
            self.hub.validate_params(tool, extraction)

    def test_int32_type(self):
        from conftest import make_tool, make_param
        tool = make_tool("test", [make_param("count", "int32")])
        extraction = {"count": "5"}
        converted, missing = self.hub.validate_params(tool, extraction)
        assert len(missing) == 0
        assert converted["count"] == 5

    def test_already_int_passes(self):
        from conftest import make_tool, make_param
        tool = make_tool("test", [make_param("id", "int64")])
        extraction = {"id": 42}
        converted, missing = self.hub.validate_params(tool, extraction)
        assert len(missing) == 0
        assert converted["id"] == 42

    def test_already_float_passes(self):
        from conftest import make_tool, make_param
        tool = make_tool("test", [make_param("price", "double")])
        extraction = {"price": 99.99}
        converted, missing = self.hub.validate_params(tool, extraction)
        assert len(missing) == 0


class TestExtractionParamsMore:
    """extraction_params_with_retry 更多场景"""

    @classmethod
    def setup_class(cls):
        from param_extraction.param_extraction_hub import ParamExtractionHub
        cls.hub = ParamExtractionHub.__new__(ParamExtractionHub)
        cls.hub.LargeLanguageModel = MagicMock()
        cls.hub.PromptModelHub = MagicMock()
        cls.hub.model = "test"
        cls.hub.temperature = 0.01
        cls.hub.top_p = 0.01

    def test_extraction_params_delegates_to_retry(self):
        """extraction_params 委托到 extraction_params_with_retry"""
        from conftest import make_tool, make_param

        self.hub.LargeLanguageModel.chat_completions.return_value = '{"name": "test"}'
        self.hub.PromptModelHub.gen_get_all_parameters_prompt.return_value = "prompt"
        self.hub.PromptModelHub.post_process_get_all_parameter_result.return_value = {"name": "test"}

        tool = make_tool("test", [make_param("name", "string")])
        results, missing = self.hub.extraction_params("查询", tool)
        assert results == {"name": "test"}
        assert missing == []

    def test_post_process_returns_none_triggers_retry(self):
        """post_process 返回 None → 触发重试"""
        from conftest import make_tool, make_param

        self.hub.LargeLanguageModel.chat_completions.side_effect = [
            "invalid response",
            '{"name": "retry_ok"}',
        ]
        self.hub.PromptModelHub.gen_get_all_parameters_prompt.return_value = "prompt"
        self.hub.PromptModelHub.post_process_get_all_parameter_result.side_effect = [
            None,  # 第一次失败
            {"name": "retry_ok"},
        ]

        tool = make_tool("test", [make_param("name", "string")])
        results, missing = self.hub.extraction_params_with_retry("查询", tool)
        assert results == {"name": "retry_ok"}

    def test_pydantic_error_triggers_retry(self):
        """Pydantic ValidationError 触发重试（覆盖第 123-126 行）"""
        from conftest import make_tool, make_param
        from pydantic import ValidationError

        self.hub.PromptModelHub.gen_get_all_parameters_prompt.return_value = "prompt"
        self.hub.LargeLanguageModel.chat_completions.side_effect = [
            "{invalid json}",  # post_process 会返回空 dict
            '{"name": "correct"}',
        ]
        # 第一次：post_process 返回 {"name": 123}，validate_params 会抛 ValidationError
        # 第二次：post_process 返回 {"name": "correct"}，校验通过
        self.hub.PromptModelHub.post_process_get_all_parameter_result.side_effect = [
            {"name": 123},       # int 但参数类型是 string → ValidationError
            {"name": "correct"},
        ]

        tool = make_tool("test", [make_param("name", "string")])
        results, missing = self.hub.extraction_params_with_retry("查询", tool)
        assert results == {"name": "correct"}
        assert missing == []


class TestParamExtractionNoRetry:
    """_extraction_params_no_retry 测试（覆盖第 151-157 行）"""

    @classmethod
    def setup_class(cls):
        from param_extraction.param_extraction_hub import ParamExtractionHub
        cls.hub = ParamExtractionHub.__new__(ParamExtractionHub)
        cls.hub.LargeLanguageModel = MagicMock()
        cls.hub.PromptModelHub = MagicMock()
        cls.hub.model = "test"
        cls.hub.temperature = 0.01
        cls.hub.top_p = 0.01
        from conftest import make_tool, make_param
        cls.tool = make_tool("test_no_retry", [make_param("name", "string")])

    def test_no_retry_calls_directly(self):
        """直接调用无重试版本，验证走通"""
        self.hub.LargeLanguageModel.chat_completions.return_value = '{"name": "apple"}'
        self.hub.PromptModelHub.gen_get_all_parameters_prompt.return_value = "prompt"
        self.hub.PromptModelHub.post_process_get_all_parameter_result.return_value = {"name": "apple"}
        results, missing = self.hub._extraction_params_no_retry("查询", self.tool)
        assert results == {"name": "apple"}
        assert missing == []

    def test_no_retry_with_pydantic_validation_error(self):
        """_extraction_params_no_retry 传入非法值时 Pydantic 抛 ValidationError"""
        self.hub.LargeLanguageModel.chat_completions.return_value = '{"name": 123}'
        self.hub.PromptModelHub.gen_get_all_parameters_prompt.return_value = "prompt"
        self.hub.PromptModelHub.post_process_get_all_parameter_result.return_value = {"name": 123}
        import pytest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            self.hub._extraction_params_no_retry("查询", self.tool)
