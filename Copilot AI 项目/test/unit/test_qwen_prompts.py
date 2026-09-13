"""测试 Qwen 专用 Prompt 覆盖"""

import pytest
from unittest.mock import MagicMock, patch


class TestQwenPromptOverrides:
    """Qwen 模型专用 prompt 模板"""

    @classmethod
    def setup_class(cls):
        from prompt.qwen_model_prompts import QwenModelPromptHub
        cls.hub = QwenModelPromptHub("", "qwen-max-0919")

    def test_has_both_version_constants(self):
        from prompt.qwen_model_prompts import QwenModelPromptHub
        assert QwenModelPromptHub.VERSION_QWEN_TOOL_SELECTION == "v1.0"
        assert QwenModelPromptHub.VERSION_QWEN_PARAM_EXTRACTION == "v1.0"

    def test_get_root_task_prompt_text(self):
        text = self.hub.get_root_task_prompt_text()
        assert "API tool planning expert" in text
        assert "is_single" in text
        assert "{query}" in text
        assert "{tool_descs}" in text

    def test_get_param_task_prompt_text(self):
        text = self.hub.get_param_task_prompt_text()
        assert "API tool invocation master" in text
        assert "{query}" in text
        assert "{params}" in text
        assert "{missing_param}" in text

    def test_gen_root_task_prompt_with_empty_query(self):
        result = self.hub.gen_root_task_prompt("", [])
        assert result is None

    def test_gen_root_task_prompt_with_query(self):
        from conftest import make_tool, make_param
        tools = [make_tool("tool1", [make_param("p1", "string")])]
        tools[0].name_for_model = "tool1"
        tools[0].name_for_human = "查询产品"
        tools[0].description = "查询产品信息"
        prompt = self.hub.gen_root_task_prompt("测试查询", tools)
        assert prompt is not None
        assert "测试查询" in prompt

    def test_gen_param_task_prompt(self):
        prompt = self.hub.gen_param_task_prompt("测试", '{"p1":"v1"}', "supplierId: 供应商ID")
        assert prompt is not None
        assert "测试" in prompt

    def test_gen_subtask_context_prompt_with_empty_query(self):
        result = self.hub.gen_subtask_context_prompt("", [])
        assert result is None

    def test_gen_subtask_context_prompt(self):
        context = [{"label": "tool1", "result": "ok", "task_description": "test task"}]
        prompt = self.hub.gen_subtask_context_prompt("测试查询", context)
        assert prompt is not None
        assert "测试查询" in prompt
        assert "tool1" in prompt

    def test_get_all_parameters_prompt_text(self):
        text = self.hub.get_all_parameters_prompt_text()
        assert "arguments" in text
        assert "{query}" in text
        assert "{arguments}" in text

    def test_inherits_base_versions(self):
        from prompt.general_prompts import PromptModelHub
        assert self.hub.VERSION_ROOT_TASK == "v2.0"
        assert self.hub.VERSION_TOOL_SELECTION == "v2.0"

    def test_desc_attribute_set(self):
        assert "qwen" in self.hub.use_desc.lower()
