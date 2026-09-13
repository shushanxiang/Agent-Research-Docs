"""测试 GenerateTaskHub — 任务生成"""

import pytest
from unittest.mock import MagicMock, patch


class TestGenerateTaskHub:
    """任务生成测试"""

    @classmethod
    def setup_class(cls):
        # Mock 初始化，避免 MongoDB/Milvus 依赖
        with patch("tasks.generate_task_hub.LargeLanguageModel"), \
             patch("tasks.generate_task_hub.create_prompt_hub"), \
             patch("tasks.generate_task_hub.ToolManager"):
            from tasks.generate_task_hub import GenerateTaskHub
            cls.hub_cls = GenerateTaskHub
            cls.hub = GenerateTaskHub.__new__(GenerateTaskHub)
            cls.hub.LargeLanguageModel = MagicMock()
            cls.hub.PromptModelHub = MagicMock()
            cls.hub.ToolManager = MagicMock()
            cls.hub.model = "test-model"
            cls.hub.temperature = 0.01
            cls.hub.top_p = 0.01

    def test_gen_root_task_single(self):
        """单任务判断"""
        self.hub.LargeLanguageModel.chat_completions.return_value = "Single API tool task: Yes"
        self.hub.PromptModelHub.gen_root_task_prompt.return_value = "prompt"
        self.hub.PromptModelHub.post_process_gen_root_task.return_value = (True, None)
        self.hub.ToolManager.get_raw_all_tools.return_value = []

        is_single, desc = self.hub.gen_root_task("查询苹果")
        assert is_single is True
        assert desc is None

    def test_gen_root_task_multi(self):
        """多任务判断"""
        self.hub.LargeLanguageModel.chat_completions.return_value = "Single API tool task: No\nFirst subtask: 查询苹果"
        self.hub.PromptModelHub.gen_root_task_prompt.return_value = "prompt"
        self.hub.PromptModelHub.post_process_gen_root_task.return_value = (False, "查询苹果")
        self.hub.ToolManager.get_raw_all_tools.return_value = []

        is_single, desc = self.hub.gen_root_task("查询苹果和梨子")
        assert is_single is False
        assert desc == "查询苹果"

    def test_gen_param_task(self):
        """参数补全任务"""
        self.hub.LargeLanguageModel.chat_completions.return_value = "查询物流供应商信息"
        self.hub.PromptModelHub.gen_param_task_prompt.return_value = "prompt"

        result = self.hub.gen_param_task("原始查询", '{"quantity": 1}', "supplierId: 供应商ID")
        assert result == "查询物流供应商信息"

    def test_gen_from_context_task_complete(self):
        """基于上下文生成子任务 — 已完成"""
        self.hub.LargeLanguageModel.chat_completions.return_value = "Task completed: Yes"
        self.hub.PromptModelHub.gen_subtask_context_prompt.return_value = "prompt"
        self.hub.PromptModelHub.post_process_gen_subtask_task.return_value = (True, None)

        flag, desc = self.hub.gen_from_context_task("查询任务", [{"label": "t1", "result": "ok"}])
        assert flag is True
        assert desc is None

    def test_gen_from_context_task_continue(self):
        """基于上下文生成子任务 — 继续"""
        self.hub.LargeLanguageModel.chat_completions.return_value = "Task completed: No\nNext subtask: 查询梨子"
        self.hub.PromptModelHub.gen_subtask_context_prompt.return_value = "prompt"
        self.hub.PromptModelHub.post_process_gen_subtask_task.return_value = (False, "查询梨子")

        flag, desc = self.hub.gen_from_context_task("查询任务", [{"label": "t1", "result": "ok"}])
        assert flag is False
        assert desc == "查询梨子"

    def test_gen_context_request_task(self):
        """上下文请求任务"""
        self.hub.LargeLanguageModel.chat_completions.return_value = "用户想要查询产品信息"
        self.hub.PromptModelHub.gen_context_request.return_value = "prompt"

        result = self.hub.gen_context_request_task([{"role": "user", "content": "查询苹果"}])
        assert result == "用户想要查询产品信息"

    def test_gen_judge_task_not_validate(self):
        """不需要验证的工具直接返回 False"""
        from conftest import make_tool, make_param
        tool = make_tool("safe_tool", [make_param("name", "string")], is_validate=False)

        flag, reason = self.hub.gen_judge_task("query", tool, {"name": "value"})
        assert flag is False
        assert reason is None

    def test_gen_judge_task_validate_safe(self):
        """需要验证的工具 — 安全"""
        from conftest import make_tool, make_param
        tool = make_tool("sensitive_tool", [make_param("quantity", "int32")], is_validate=True)

        self.hub.LargeLanguageModel.chat_completions.return_value = "Whether to inject: No\nReason: 参数合理"
        self.hub.PromptModelHub.judge_validate.return_value = "prompt"
        self.hub.PromptModelHub.post_process_gen_judge_task.return_value = (False, None)

        flag, reason = self.hub.gen_judge_task("query", tool, {"quantity": 10})
        assert flag is False
        assert reason is None

    def test_gen_judge_task_validate_attack(self):
        """需要验证的工具 — 检测到攻击"""
        from conftest import make_tool, make_param
        tool = make_tool("sensitive_tool", [make_param("quantity", "int32")], is_validate=True)

        self.hub.LargeLanguageModel.chat_completions.return_value = "Whether to inject: Yes\nReason: 参数为负数"
        self.hub.PromptModelHub.judge_validate.return_value = "prompt"
        self.hub.PromptModelHub.post_process_gen_judge_task.return_value = (True, "参数为负数")

        flag, reason = self.hub.gen_judge_task("query", tool, {"quantity": -10})
        assert flag is True
        assert reason == "参数为负数"
