"""全面测试 ToolSummaryHub"""

import os
import sys
import pytest
from unittest.mock import MagicMock

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


class TestToolSummaryHubFull:
    """ToolSummaryHub 完整测试"""

    @classmethod
    def setup_class(cls):
        from tools.tool_summary_hub import ToolSummaryHub
        hub = ToolSummaryHub.__new__(ToolSummaryHub)
        hub.LargeLanguageModel = MagicMock()
        hub.LargeLanguageModel.chat_completions.return_value = "摘要内容"
        hub.PromptModelHub = MagicMock()
        hub.PromptModelHub.gen_tool_summary_prompt.return_value = "prompt"
        hub.PromptModelHub.chunk_tool_summary_prompt.return_value = "chunk prompt"
        hub.model = "test-model"
        hub.temperature = 0.01
        hub.top_p = 0.01
        cls.hub = hub

    def test_split_string_by_length_divisible(self):
        result = self.hub.split_string_by_length("abcdef", 2)
        assert result == ["ab", "cd", "ef"]

    def test_split_string_by_length_remainder(self):
        result = self.hub.split_string_by_length("abcde", 2)
        assert result == ["ab", "cd", "e"]

    def test_split_string_by_length_shorter(self):
        result = self.hub.split_string_by_length("abc", 100)
        assert result == ["abc"]

    def test_split_string_by_length_empty(self):
        result = self.hub.split_string_by_length("", 10)
        assert isinstance(result, list)

    def test_summary_large_result_all_small(self):
        apis = [{"result": "small", "tool": "t1", "task_description": "d1"}]
        result = self.hub.summary_large_result("query", apis)
        assert result == apis

    def test_summary_large_result_one_large(self):
        large = "x" * 100001
        apis = [{"result": large, "tool": "t1", "task_description": "d1"}]
        result = self.hub.summary_large_result("query", apis)
        assert result[0]["result"] != large
        assert "摘要内容" in result[0]["result"]

    def test_summary_large_result_mixed(self):
        large = "y" * 100001
        apis = [
            {"result": "small", "tool": "t1", "task_description": "d1"},
            {"result": large, "tool": "t2", "task_description": "d2"},
        ]
        result = self.hub.summary_large_result("query", apis)
        assert result[0]["result"] == "small"
        assert result[1]["result"] != large

    def test_tool_summary(self):
        apis = [{"result": "data", "tool": "t1", "task_description": "d1"}]
        result = self.hub.tool_summary("测试查询", apis)
        assert result == "摘要内容"

    def test_tool_summary_with_large_data(self):
        large = "z" * 100001
        apis = [{"result": large, "tool": "t1", "task_description": "d1"}]
        result = self.hub.tool_summary("查询", apis)
        assert result == "摘要内容"
