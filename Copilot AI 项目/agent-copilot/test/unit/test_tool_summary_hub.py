"""测试 ToolSummaryHub — 结果摘要和分片"""

import pytest
from unittest.mock import MagicMock


class MockToolSummaryHub:
    """直接测试 ToolSummaryHub 的核心逻辑"""

    @classmethod
    def setup_class(cls):
        from tools.tool_summary_hub import ToolSummaryHub
        cls.ToolSummaryHub = ToolSummaryHub

    def test_split_string_by_length_divisible(self):
        """字符串长度刚好被整除"""
        from tools.tool_summary_hub import ToolSummaryHub
        hub = ToolSummaryHub.__new__(ToolSummaryHub)
        result = hub.split_string_by_length("abcdef", 2)
        assert result == ["ab", "cd", "ef"]

    def test_split_string_by_length_with_remainder(self):
        """字符串长度不能被整除"""
        from tools.tool_summary_hub import ToolSummaryHub
        hub = ToolSummaryHub.__new__(ToolSummaryHub)
        result = hub.split_string_by_length("abcde", 2)
        assert result == ["ab", "cd", "e"]

    def test_split_string_by_length_shorter_than_limit(self):
        """字符串长度小于切分长度"""
        from tools.tool_summary_hub import ToolSummaryHub
        hub = ToolSummaryHub.__new__(ToolSummaryHub)
        result = hub.split_string_by_length("abc", 10)
        assert result == ["abc"]

    def test_split_string_by_length_empty(self):
        """空字符串"""
        from tools.tool_summary_hub import ToolSummaryHub
        hub = ToolSummaryHub.__new__(ToolSummaryHub)
        result = hub.split_string_by_length("", 10)
        assert result == [""]

    def test_summary_large_result_all_small(self):
        """所有结果都小于阈值，直接返回"""
        from tools.tool_summary_hub import ToolSummaryHub
        hub = ToolSummaryHub.__new__(ToolSummaryHub)
        apis = [{"result": "short", "tool": "t1", "task_description": "d1"}]
        result = hub.summary_large_result("query", apis)
        assert result == apis

    def test_summary_large_result_one_large(self):
        """有一个大数据结果需要分片摘要"""
        from tools.tool_summary_hub import ToolSummaryHub
        hub = ToolSummaryHub.__new__(ToolSummaryHub)
        hub.LargeLanguageModel = MagicMock()
        hub.LargeLanguageModel.chat_completions.return_value = "summary"
        hub.PromptModelHub = MagicMock()
        hub.PromptModelHub.chunk_tool_summary_prompt.return_value = "chunk prompt"
        hub.model = "test-model"
        hub.temperature = 0.01
        hub.top_p = 0.01

        large_result = "x" * 100001
        apis = [{"result": large_result, "tool": "t1", "task_description": "d1"}]
        result = hub.summary_large_result("query", apis)
        # 结果应该被摘要替换
        assert result[0]["result"] != large_result
        assert "summary" in result[0]["result"]

    def test_summary_large_result_small_is_skipped(self):
        """小结果和超标结果混合"""
        from tools.tool_summary_hub import ToolSummaryHub
        hub = ToolSummaryHub.__new__(ToolSummaryHub)
        hub.LargeLanguageModel = MagicMock()
        hub.LargeLanguageModel.chat_completions.return_value = "summary_chunk"
        hub.PromptModelHub = MagicMock()
        hub.PromptModelHub.chunk_tool_summary_prompt.return_value = "prompt"
        hub.model = "test-model"
        hub.temperature = 0.01
        hub.top_p = 0.01

        large_result = "y" * 100001
        apis = [
            {"result": "short result", "tool": "t1", "task_description": "d1"},
            {"result": large_result, "tool": "t2", "task_description": "d2"},
        ]
        result = hub.summary_large_result("query", apis)
        assert result[0]["result"] == "short result"  # 不变
        assert result[1]["result"] != large_result  # 被摘要

    def test_tool_summary_basic(self):
        """基本摘要流程"""
        from tools.tool_summary_hub import ToolSummaryHub
        hub = ToolSummaryHub.__new__(ToolSummaryHub)
        hub.LargeLanguageModel = MagicMock()
        hub.LargeLanguageModel.chat_completions.return_value = "最终摘要"
        hub.PromptModelHub = MagicMock()
        hub.PromptModelHub.gen_tool_summary_prompt.return_value = "总结 prompt"
        hub.model = "test-model"
        hub.temperature = 0.01
        hub.top_p = 0.01

        apis = [{"result": "data", "tool": "t1", "task_description": "d1"}]
        result = hub.tool_summary("查询", apis)
        assert result == "最终摘要"
