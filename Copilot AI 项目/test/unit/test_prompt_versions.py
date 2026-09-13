"""测试 prompt_versions.py"""

import pytest


class TestPromptVersionSnapshot:
    """Prompt 版本注册表"""

    def test_snapshot_has_all_keys(self):
        from utils.prompt_versions import get_prompt_version_snapshot
        snapshot = get_prompt_version_snapshot()
        assert len(snapshot) >= 10
        assert snapshot["tool_selection"]["version"] == "v2.0"
        assert snapshot["tool_selection"]["class"] == "PromptModelHub"
        assert snapshot["param_extraction"]["version"] == "v2.0"

    def test_version_source_in_code(self):
        from utils.prompt_versions import get_prompt_version_snapshot
        from prompt.general_prompts import PromptModelHub
        snapshot = get_prompt_version_snapshot()
        assert PromptModelHub.VERSION_TOOL_SELECTION == snapshot["tool_selection"]["version"]
        assert PromptModelHub.VERSION_ROOT_TASK == snapshot["root_task"]["version"]

    def test_qwen_versions(self):
        """千问覆盖版本号：Qwen 类实际 override 了 4 个方法"""
        from utils.prompt_versions import get_prompt_version_snapshot
        from prompt.qwen_model_prompts import QwenModelPromptHub
        snapshot = get_prompt_version_snapshot()
        # Qwen 覆盖的 4 个方法都有专用版本号
        assert snapshot["qwen_root_task"]["version"] == "v1.0"
        assert snapshot["qwen_param_task"]["version"] == "v1.0"
        assert snapshot["qwen_subtask_context"]["version"] == "v1.0"
        assert snapshot["qwen_param_extraction"]["version"] == "v1.0"
        # 版本号源头一致性
        assert QwenModelPromptHub.VERSION_QWEN_PARAM_EXTRACTION == snapshot["qwen_param_extraction"]["version"]
        assert QwenModelPromptHub.VERSION_QWEN_ROOT_TASK == snapshot["qwen_root_task"]["version"]

    def test_model_config_entry(self):
        from utils.prompt_versions import get_prompt_version_snapshot
        snapshot = get_prompt_version_snapshot()
        assert "model_config" in snapshot
        assert snapshot["model_config"]["version"] == "v1.0"

    def test_all_base_versions_start_v1(self):
        from utils.prompt_versions import get_prompt_version_snapshot
        snapshot = get_prompt_version_snapshot()
        base_keys = ["root_task", "subtask_context", "tool_selection", "param_task",
                     "param_extraction", "tool_summary", "chunk_summary", "injection_judge"]
        for key in base_keys:
            assert snapshot[key]["version"].startswith("v"), f"{key} version should start with v"
