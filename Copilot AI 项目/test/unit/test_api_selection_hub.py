"""测试 ApiSelectionHub — 全分支 mock 覆盖

覆盖 get_tool_coarse_and_fine 的：
- 向量检索空结果快速失败
- 重排序空结果快速失败
- LLM 精选成功（required_argument=None）
- LLM 精选成功（required_argument=非空）
- 异常处理路径
"""

import pytest
from unittest.mock import MagicMock, patch


class TestApiSelectionHub:

    @classmethod
    def setup_class(cls):
        """构造 ApiSelectionHub 实例，所有外部依赖 mock"""
        with patch.multiple(
            "apis.api_selection_hub",
            CustomizeMilvus=MagicMock,
            LargeLanguageModel=MagicMock,
            PromptModelHub=MagicMock,
            ToolManager=MagicMock,
        ):
            from apis.api_selection_hub import ApiSelectionHub
            cls.hub = ApiSelectionHub.__new__(ApiSelectionHub)
            cls.hub.milvus = MagicMock()
            cls.hub.LargeLanguageModel = MagicMock()
            cls.hub.ToolManager = MagicMock()
            cls.hub.model = "test-model"
            cls.hub.temperature = 0.01
            cls.hub.top_p = 0.01

        # 构造 PromptModelHub 实例用于 post_process
        from prompt.general_prompts import PromptModelHub
        cls.hub.PromptModelHub = PromptModelHub("")

    def test_vector_search_returns_empty(self):
        """向量检索无结果 → 快速失败返回 None"""
        self.hub.milvus.get_docs.return_value = []
        result = self.hub.get_tool_coarse_and_fine("不存在的查询", None, topK=5)
        assert result is None

    def test_rerank_returns_empty(self):
        """重排序无结果 → 快速失败返回 None"""
        self.hub.milvus.get_docs.return_value = [1, 2]

        from conftest import make_tool
        fake_tools = [make_tool("tool1"), make_tool("tool2")]
        self.hub.ToolManager.get_tools_by_ids.return_value = fake_tools
        self.hub.ToolManager.search_tools_with_rerank.return_value = []

        result = self.hub.get_tool_coarse_and_fine("查询", None, topK=5)
        assert result is None

    def test_llm_selects_tool_without_required_arg(self):
        """LLM 精选成功（required_argument=None）"""
        self.hub.milvus.get_docs.return_value = [1]

        from conftest import make_tool
        fake_tools = [make_tool("tool1")]
        self.hub.ToolManager.get_tools_by_ids.return_value = fake_tools
        self.hub.ToolManager.search_tools_with_rerank.return_value = fake_tools

        from conftest import make_tool as mk
        expected_tool = mk("selected_tool")
        self.hub.PromptModelHub.post_process_tool_selection_result_with_retry = MagicMock(
            return_value=expected_tool
        )

        result = self.hub.get_tool_coarse_and_fine("查询", None, topK=5)
        assert result is expected_tool

    def test_llm_selects_tool_with_required_arg(self):
        """LLM 精选成功（required_argument 非空）"""
        self.hub.milvus.get_docs.return_value = [1]

        from conftest import make_tool
        fake_tools = [make_tool("tool1")]
        self.hub.ToolManager.get_tools_by_ids.return_value = fake_tools
        self.hub.ToolManager.search_tools_with_rerank.return_value = fake_tools

        from conftest import make_tool as mk
        expected_tool = mk("selected_tool")
        self.hub.PromptModelHub.post_process_tool_selection_result_with_retry = MagicMock(
            return_value=expected_tool
        )

        # required_argument 非空 → 走 else 分支
        result = self.hub.get_tool_coarse_and_fine("查询", "supplierId", topK=5)
        assert result is expected_tool

    def test_llm_returns_none(self):
        """LLM 未选出工具 → 返回 None"""
        self.hub.milvus.get_docs.return_value = [1]

        from conftest import make_tool
        fake_tools = [make_tool("tool1")]
        self.hub.ToolManager.get_tools_by_ids.return_value = fake_tools
        self.hub.ToolManager.search_tools_with_rerank.return_value = fake_tools

        self.hub.PromptModelHub.post_process_tool_selection_result_with_retry = MagicMock(
            return_value=None
        )

        result = self.hub.get_tool_coarse_and_fine("查询", None, topK=5)
        assert result is None

    def test_exception_handling(self):
        """异常路径 → 返回 None"""
        self.hub.milvus.get_docs.side_effect = RuntimeError("Milvus 连接失败")

        result = self.hub.get_tool_coarse_and_fine("查询", None, topK=5)
        assert result is None
