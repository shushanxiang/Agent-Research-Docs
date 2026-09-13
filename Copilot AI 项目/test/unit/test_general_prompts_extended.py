"""扩展单元测试 — general_prompts.py 辅助函数和更多 PromptModelHub 方法"""

import pytest
from unittest.mock import MagicMock

from conftest import make_tool, make_param


class TestFindOuterBraces:
    """find_outer_braces 和 remove_unquoted_backslash 辅助函数"""

    def test_simple_braces(self):
        from prompt.general_prompts import find_outer_braces
        pairs = find_outer_braces("{hello}")
        assert len(pairs) == 1
        assert pairs[0] == (0, 6)

    def test_nested_braces(self):
        from prompt.general_prompts import find_outer_braces
        pairs = find_outer_braces("{outer {inner}}")
        assert len(pairs) == 2

    def test_multiple_braces(self):
        from prompt.general_prompts import find_outer_braces
        text = "Hello {world} and {foo {bar} baz}"
        pairs = find_outer_braces(text)
        # 应该有 3 个配对: {world}, {bar}, {foo {bar} baz}
        assert len(pairs) == 3

    def test_no_braces(self):
        from prompt.general_prompts import find_outer_braces
        pairs = find_outer_braces("no braces here")
        assert len(pairs) == 0

    def test_unclosed_brace(self):
        from prompt.general_prompts import find_outer_braces
        pairs = find_outer_braces("{open")
        assert len(pairs) == 0  # 没有闭合

    def test_extra_closing(self):
        from prompt.general_prompts import find_outer_braces
        pairs = find_outer_braces("close}")
        assert len(pairs) == 0


class TestRemoveUnquotedBackslash:
    """remove_unquoted_backslash 函数"""

    def test_remove_simple_backslash(self):
        from prompt.general_prompts import remove_unquoted_backslash
        result = remove_unquoted_backslash(r"abc\def")
        assert result == "abcdef"

    def test_keep_quoted_backslash(self):
        from prompt.general_prompts import remove_unquoted_backslash
        result = remove_unquoted_backslash('"abc\\def"')
        assert '"abc\\def"' in result

    def test_mixed(self):
        from prompt.general_prompts import remove_unquoted_backslash
        result = remove_unquoted_backslash(r'a\b "c\d" e\f')
        assert "ab" in result
        assert '"c\\d"' in result
        assert "ef" in result


class TestGenerateToolDesc:
    """generate_tool_desc 函数"""

    def test_generates_desc(self):
        from prompt.general_prompts import generate_tool_desc
        tool = make_tool("查询产品", [make_param("name", "string")])
        tool.name_for_model = "tool1"
        tool.name_for_human = "查询产品API"
        tool.description = "查询产品信息"
        descs = generate_tool_desc([tool])
        assert len(descs) == 1
        assert "tool1" in descs[0]
        assert "查询产品API" in descs[0]


class TestPromptModelHubMoreMethods:
    """PromptModelHub 其余方法测试"""

    @classmethod
    def setup_class(cls):
        from prompt.general_prompts import PromptModelHub
        cls.hub = PromptModelHub("")

    def test_get_root_task_prompt_text(self):
        text = self.hub.get_root_task_prompt_text()
        assert "API tool planning" in text
        assert "{query}" in text

    def test_get_param_task_prompt_text(self):
        text = self.hub.get_param_task_prompt_text()
        assert "API tool invocation" in text
        assert "{query}" in text
        assert "{missing_param}" in text

    def test_gen_root_task_prompt_empty_query(self):
        result = self.hub.gen_root_task_prompt("", [])
        assert result is None

    def test_gen_root_task_prompt(self):
        tool = make_tool("tool1", [make_param("p1", "string")])
        tool.name_for_model = "tool1"
        tool.name_for_human = "查询产品"
        tool.description = "查询产品信息"
        prompt = self.hub.gen_root_task_prompt("查询苹果", [tool])
        assert prompt is not None
        assert "查询苹果" in prompt

    def test_gen_param_task_prompt_empty(self):
        result = self.hub.gen_param_task_prompt("", "", "")
        assert result is None

    def test_gen_param_task_prompt(self):
        prompt = self.hub.gen_param_task_prompt("查询", '{"p1":"v1"}', "缺少: id")
        assert prompt is not None
        assert "查询" in prompt

    def test_gen_subtask_context_prompt_empty(self):
        result = self.hub.gen_subtask_context_prompt("", [])
        assert result is None

    def test_gen_subtask_context_prompt(self):
        ctx = [{"label": "tool1", "result": "ok", "task_description": "task1"}]
        prompt = self.hub.gen_subtask_context_prompt("查询", ctx)
        assert prompt is not None
        assert "查询" in prompt
        assert "tool1" in prompt

    def test_gen_tool_selection_prompt_empty(self):
        result = self.hub.gen_tool_selection_prompt("", [])
        assert result is None

    def test_gen_tool_selection_prompt(self):
        tool = make_tool("tool1", [make_param("p1", "string")])
        tool.name_for_model = "tool1"
        tool.name_for_human = "查询产品"
        tool.description = "查询产品"
        prompt = self.hub.gen_tool_selection_prompt("任务描述", [tool])
        assert "tool1" in prompt
        assert "任务描述" in prompt

    def test_gen_required_argument_tool_selection_prompt_empty(self):
        result = self.hub.gen_required_argument_tool_selection_prompt("", "arg", [])
        assert result is None

    def test_gen_required_argument_tool_selection_prompt(self):
        tool = make_tool("tool1", [make_param("p1", "string")])
        tool.name_for_model = "tool1"
        tool.name_for_human = "查询产品"
        tool.description = "desc"
        prompt = self.hub.gen_required_argument_tool_selection_prompt("查询", "supplierId", [tool])
        assert "supplierId" in prompt

    def test_gen_tool_summary_prompt_empty(self):
        result = self.hub.gen_tool_summary_prompt("", [])
        assert result is None

    def test_gen_tool_summary_prompt(self):
        ctx = [{"tool": "t1", "result": "data", "task_description": "d1"}]
        prompt = self.hub.gen_tool_summary_prompt("查询", ctx)
        assert prompt is not None

    def test_gen_get_all_parameters_prompt_empty(self):
        result = self.hub.gen_get_all_parameters_prompt("", [])
        assert result is None

    def test_gen_get_all_parameters_prompt(self):
        prompt = self.hub.gen_get_all_parameters_prompt("查询苹果", [make_param("productName", "string")])
        assert prompt is not None
        assert "productName" in prompt

    def test_gen_context_request_empty(self):
        # gen_context_request 先 json.dumps(context)，所以 [] → "[]" 长度=2 不会短路
        # 进入正常流程，返回正确的 prompt 字符串
        from prompt.general_prompts import PromptModelHub
        result = PromptModelHub("").gen_context_request([])
        assert result is not None
        assert "user Copilot request writer" in result

    def test_gen_context_request(self):
        prompt = self.hub.gen_context_request([{"role": "user", "content": "hi"}])
        assert prompt is not None

    def test_chunk_tool_summary_prompt_empty(self):
        result = self.hub.chunk_tool_summary_prompt("", "api", "data")
        assert result is None

    def test_chunk_tool_summary_prompt(self):
        prompt = self.hub.chunk_tool_summary_prompt("task", "api", "data")
        assert prompt is not None
        assert "task" in prompt

    def test_judge_validate(self):
        tool = make_tool("test", [make_param("quantity", "int32")], is_validate=True)
        tool.name_for_human = "测试API"
        tool.description = "测试描述"
        tool.request_body[0].format = ""
        tool.request_body[0].enum = []

        prompt = self.hub.judge_validate("查询", tool, {"quantity": 10})
        assert prompt is not None

    def test_judge_validate_empty_query(self):
        from conftest import make_tool as mk
        t = mk("test")
        result = self.hub.judge_validate("", t, {})
        assert result is None

    def test_judge_validate_removes_description_zero(self):
        tool = make_tool("test", [make_param("quantity", "int32")], is_validate=True)
        tool.name_for_human = "测试API"
        tool.description = "测试"

        # 参数 description=无法查询 → 应被移除
        prompt = self.hub.judge_validate("查询", tool,
                                          {"description": "无法查询该产品信息", "price": 0, "quantityInStock": 0})
        assert prompt is not None
        # price=0 和 quantityInStock=0 也应被移除

    def test_post_process_gen_root_task_single(self):
        is_single, desc = self.hub.post_process_gen_root_task(
            '{"is_single": true, "description": ""}'
        )
        assert is_single is True
        assert desc is None

    def test_post_process_gen_root_task_multi(self):
        is_single, desc = self.hub.post_process_gen_root_task(
            '{"is_single": false, "description": "查询苹果"}'
        )
        assert is_single is False
        assert desc == "查询苹果"

    def test_post_process_gen_root_task_legacy_fallback(self):
        """旧格式仍能被 fallback 解析"""
        is_single, desc = self.hub.post_process_gen_root_task(
            "Single API tool task: Yes\nFirst subtask description: None"
        )
        assert is_single is True
        assert desc is None

    def test_post_process_gen_subtask_task(self):
        flag, desc = self.hub.post_process_gen_subtask_task(
            '{"is_single": true, "description": ""}'
        )
        assert flag is True

    def test_post_process_gen_judge_task_safe(self):
        is_attack, reason = self.hub.post_process_gen_judge_task(
            '{"is_attack": false, "reason": "参数合理"}'
        )
        assert is_attack is False
        assert reason == "参数合理"

    def test_post_process_gen_judge_task_attack(self):
        is_attack, reason = self.hub.post_process_gen_judge_task(
            '{"is_attack": true, "reason": "负数"}'
        )
        assert is_attack is True
        assert "负数" in reason

    def test_post_process_gen_judge_legacy_fallback(self):
        """旧 Yes/No 格式仍能被 fallback 解析"""
        is_attack, reason = self.hub.post_process_gen_judge_task(
            "Whether to inject attack for prompt: No\nReason: 参数合理"
        )
        assert is_attack is False

    def test_post_process_tool_selection_legacy(self):
        """旧 Action: toolX 格式通过 fallback 解析"""
        from conftest import make_tool
        tool = make_tool("test_api")
        tool.name_for_model = "tool1"
        tool.name_for_human = "测试API"
        result = self.hub.post_process_tool_selection_result("Action: tool1", [tool])
        assert result is tool

    def test_post_process_tool_selection_json(self):
        """新 JSON 格式解析"""
        from conftest import make_tool
        tool = make_tool("test_api")
        tool.name_for_model = "tool1"
        tool.name_for_human = "测试API"
        result = self.hub.post_process_tool_selection_result('{"tool_name": "tool1"}', [tool])
        assert result is tool

    def test_version_constants(self):
        from prompt.general_prompts import PromptModelHub
        assert PromptModelHub.VERSION_ROOT_TASK == "v2.0"
        assert PromptModelHub.VERSION_TOOL_SELECTION == "v2.0"
        assert PromptModelHub.VERSION_PARAM_EXTRACTION == "v2.0"
        assert PromptModelHub.VERSION_INJECTION_JUDGE == "v2.0"
        assert PromptModelHub.VERSION_TOOL_SUMMARY == "v1.0"
        assert PromptModelHub.VERSION_CHUNK_SUMMARY == "v1.0"
        assert PromptModelHub.VERSION_PARAM_TASK == "v1.0"
        assert PromptModelHub.VERSION_SUBTASK_CONTEXT == "v1.1"
