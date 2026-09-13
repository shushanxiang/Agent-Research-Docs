"""测试 Prompt 输出解析 + 重试机制（覆盖 P0-02, P0-03）"""

import pytest
from unittest.mock import MagicMock, patch

from conftest import make_tool, make_param


class TestPostProcessToolSelection:
    """工具选择结果解析"""

    @classmethod
    def setup_class(cls):
        from prompt.general_prompts import PromptModelHub
        cls.hub = PromptModelHub("")

    def test_parse_action_format(self):
        """标准 Action: toolX 格式"""
        tools = [
            make_tool("tool1", [make_param("p1", "string")]),
            make_tool("tool2", [make_param("p2", "string")]),
        ]
        tools[0].name_for_model = "tool1"
        tools[0].name_for_human = "tool1"
        tools[1].name_for_model = "tool2"
        tools[1].name_for_human = "tool2"

        result = self.hub.post_process_tool_selection_result("Action: tool1", tools)
        assert result is not None
        assert result.name_for_model == "tool1"

    def test_parse_plain_tool_name(self):
        """无 Action 前缀的工具名"""
        tools = [
            make_tool("tool_a", [make_param("p1", "string")]),
        ]
        tools[0].name_for_model = "tool_a"
        tools[0].name_for_human = "tool_a"

        result = self.hub.post_process_tool_selection_result("tool_a", tools)
        assert result is not None
        assert result.name_for_model == "tool_a"

    def test_none_response_returns_none(self):
        """None 响应返回 stop_label"""
        result = self.hub.post_process_tool_selection_result(None, [])
        assert result is None

    def test_empty_string_returns_none(self):
        """空字符串返回 stop_label"""
        result = self.hub.post_process_tool_selection_result("", [])
        assert result is None

    def test_none_in_response_returns_none(self):
        """含有 None 的响应"""
        tools = [make_tool("tool_a", [make_param("p1", "string")])]
        tools[0].name_for_model = "tool_a"
        result = self.hub.post_process_tool_selection_result("None", tools)
        assert result is None

    def test_no_match_returns_none(self):
        """无法匹配任何工具返回 stop_label"""
        tools = [make_tool("tool_a", [make_param("p1", "string")])]
        tools[0].name_for_model = "tool_a"
        result = self.hub.post_process_tool_selection_result("Action: non_existent_tool", tools)
        assert result is None

    def test_multi_line_first_valid_wins(self):
        """多行响应取第一个有效行"""
        tools = [
            make_tool("tool_a", [make_param("p1", "string")]),
            make_tool("tool_b", [make_param("p2", "string")]),
        ]
        tools[0].name_for_model = "tool_a"
        tools[0].name_for_human = "tool_a"
        tools[1].name_for_model = "tool_b"
        tools[1].name_for_human = "tool_b"

        result = self.hub.post_process_tool_selection_result(
            "Action: tool_a\nAction: tool_b", tools
        )
        assert result is not None
        assert result.name_for_model == "tool_a"


class TestPostProcessParamExtraction:
    """参数提取结果解析"""

    @classmethod
    def setup_class(cls):
        from prompt.general_prompts import PromptModelHub
        cls.hub = PromptModelHub("")

    def test_extract_json_object(self):
        """从 LLM 输出中提取 JSON 参数"""
        tool = make_tool("test_tool", [
            make_param("productName", "string"),
            make_param("quantity", "int32"),
        ])

        answer = '{"productName": "苹果", "quantity": 10}'
        result = self.hub.post_process_get_all_parameter_result(answer, tool)
        assert result.get("productName") == "苹果"
        assert result.get("quantity") == 10

    def test_extract_json_with_markdown(self):
        """带 markdown 代码块的 JSON"""
        tool = make_tool("test_tool", [make_param("productName", "string")])

        answer = '```json\n{"productName": "苹果"}\n```'
        result = self.hub.post_process_get_all_parameter_result(answer, tool)
        assert result.get("productName") == "苹果"

    def test_match_by_description(self):
        """通过参数 description 而非 name 匹配"""
        tool = make_tool("test_tool", [make_param("product_name", "string")])
        tool.request_body[0].description = "产品名称"

        answer = '{"产品名称": "苹果"}'
        result = self.hub.post_process_get_all_parameter_result(answer, tool)
        assert result.get("product_name") == "苹果"

    def test_no_json_found_returns_empty(self):
        """无法找到 JSON 返回空 dict"""
        tool = make_tool("test_tool", [make_param("productName", "string")])

        answer = "这是一段没有 JSON 的纯文本回复"
        result = self.hub.post_process_get_all_parameter_result(answer, tool)
        assert result == {}

    def test_invalid_json_returns_empty(self):
        """非法 JSON 返回空 dict（不抛异常）"""
        tool = make_tool("test_tool", [make_param("productName", "string")])

        answer = '{productName: 苹果}'  # 非法 JSON
        result = self.hub.post_process_get_all_parameter_result(answer, tool)
        assert result == {}

    def test_multiple_braces(self):
        """含多个花括号对时提取所有"""
        tool = make_tool("test_tool", [make_param("productName", "string")])

        answer = 'Some text {"productName": "苹果"} and more {"other": 1}'
        result = self.hub.post_process_get_all_parameter_result(answer, tool)
        assert result.get("productName") == "苹果"


class TestRetrySelection:
    """工具选择重试"""

    def test_first_attempt_succeeds(self):
        """首次尝试成功不重试"""
        from prompt.general_prompts import PromptModelHub
        hub = PromptModelHub("")

        mock_llm = MagicMock()
        mock_llm.chat_completions.return_value = "Action: tool1"

        tools = [make_tool("tool1", [make_param("p1", "string")])]
        tools[0].name_for_model = "tool1"
        tools[0].name_for_human = "tool1"

        result = hub.post_process_tool_selection_result_with_retry(
            mock_llm, "test-model", 0.01, 0.01, "test task", tools, max_retries=3
        )
        assert result is not None
        assert result.name_for_model == "tool1"
        assert mock_llm.chat_completions.call_count == 1

    def test_retry_on_invalid_response(self):
        """无效响应后重试成功"""
        from prompt.general_prompts import PromptModelHub
        hub = PromptModelHub("")

        mock_llm = MagicMock()
        mock_llm.chat_completions.side_effect = [
            "invalid response",     # 第 1 次：无效
            "Action: tool2",        # 第 2 次：有效
        ]

        tools = [make_tool("tool2", [make_param("p1", "string")])]
        tools[0].name_for_model = "tool2"
        tools[0].name_for_human = "tool2"

        result = hub.post_process_tool_selection_result_with_retry(
            mock_llm, "test-model", 0.01, 0.01, "test task", tools, max_retries=3
        )
        assert result is not None
        assert result.name_for_model == "tool2"
        assert mock_llm.chat_completions.call_count == 2  # 调用了两次

    def test_all_retries_fail(self):
        """全部重试失败返回 None"""
        from prompt.general_prompts import PromptModelHub
        hub = PromptModelHub("")

        mock_llm = MagicMock()
        mock_llm.chat_completions.return_value = "garbage"

        tools = [make_tool("tool1", [make_param("p1", "string")])]
        tools[0].name_for_model = "tool1"

        result = hub.post_process_tool_selection_result_with_retry(
            mock_llm, "test-model", 0.01, 0.01, "test task", tools, max_retries=3
        )
        assert result is None
        assert mock_llm.chat_completions.call_count == 3  # 首次 1 次 + 重试 2 次各 1 次


class TestRetryParamExtraction:
    """参数提取重试"""

    def test_first_attempt_succeeds(self):
        """首次尝试成功"""
        from param_extraction.param_extraction_hub import ParamExtractionHub
        from prompt.general_prompts import PromptModelHub

        hub = ParamExtractionHub.__new__(ParamExtractionHub)
        hub.LargeLanguageModel = MagicMock()
        hub.LargeLanguageModel.chat_completions.return_value = '{"productName": "苹果"}'
        hub.PromptModelHub = PromptModelHub("")
        hub.model = "test-model"
        hub.temperature = 0.01
        hub.top_p = 0.01
        hub.validate_params = MagicMock(return_value=({"productName": "苹果"}, []))

        tool = make_tool("test_tool", [make_param("productName", "string")])

        results, missing = hub.extraction_params_with_retry("查询苹果", tool, max_retries=3)
        assert results.get("productName") == "苹果"
        assert missing == []
        assert hub.LargeLanguageModel.chat_completions.call_count == 1

    def test_all_retries_fail_returns_all_required(self):
        """全部重试失败返回空 results 和所有必填参数"""
        from param_extraction.param_extraction_hub import ParamExtractionHub
        from prompt.general_prompts import PromptModelHub

        hub = ParamExtractionHub.__new__(ParamExtractionHub)
        hub.LargeLanguageModel = MagicMock()
        hub.LargeLanguageModel.chat_completions.return_value = "not json at all"
        hub.PromptModelHub = PromptModelHub("")
        hub.model = "test-model"
        hub.temperature = 0.01
        hub.top_p = 0.01

        tool = make_tool("test_tool", [
            make_param("productName", "string"),
            make_param("quantity", "int32"),
        ])

        results, missing = hub.extraction_params_with_retry("查询苹果", tool, max_retries=2)
        assert results == {}
        assert len(missing) == 2  # 两个必填参数
        assert hub.LargeLanguageModel.chat_completions.call_count == 2

    def test_empty_model_output_triggers_retry(self):
        """空响应触发重试"""
        from param_extraction.param_extraction_hub import ParamExtractionHub
        from prompt.general_prompts import PromptModelHub

        hub = ParamExtractionHub.__new__(ParamExtractionHub)
        hub.LargeLanguageModel = MagicMock()
        hub.LargeLanguageModel.chat_completions.side_effect = [
            "",                                           # 空响应
            '{"productName": "苹果"}',                     # 重试成功
        ]
        hub.PromptModelHub = PromptModelHub("")
        hub.model = "test-model"
        hub.temperature = 0.01
        hub.top_p = 0.01
        hub.validate_params = MagicMock(return_value=({"productName": "苹果"}, []))

        tool = make_tool("test_tool", [make_param("productName", "string")])

        results, missing = hub.extraction_params_with_retry("查询苹果", tool, max_retries=3)
        assert results.get("productName") == "苹果"
        assert hub.LargeLanguageModel.chat_completions.call_count == 2
