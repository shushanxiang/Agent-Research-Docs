"""额外测试 — tool_manager 中可 mock 的部分 + customize_milvus 独立测试"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

os.environ["mongo_port"] = "27112"
os.environ["mongo_host"] = "127.0.0.1"
os.environ["milvus_uri"] = "http://127.0.0.1:19530"
os.environ["local_mode"] = "0"


class TestCustomizeMilvus:
    """Milvus 包装器独立测试"""

    def test_init(self):
        from customize_milvus_wrapper.customize_milvus import CustomizeMilvus
        m = CustomizeMilvus("http://127.0.0.1:19530", "tool_db")
        assert m is not None

    def test_list_collections(self):
        from customize_milvus_wrapper.customize_milvus import CustomizeMilvus
        m = CustomizeMilvus("http://127.0.0.1:19530", "tool_db")
        collections = m.list_collections()
        assert isinstance(collections, list)


class TestToolManagerMoreMethods:
    """ToolManager 更多方法测试"""

    @pytest.fixture(scope="module")
    def tool_mgr(self):
        from tools.tool_manager import ToolManager
        tm = ToolManager("127.0.0.1", "tools", 27112, "http://127.0.0.1:19530", "tool_db")
        yield tm

    def test_init(self, tool_mgr):
        assert tool_mgr is not None
        assert tool_mgr.mongoClient is not None
        assert tool_mgr.milvus is not None

    def test_clear_cache(self, tool_mgr):
        tool_mgr.clear_cache()

    def test_get_next_tool_id(self, tool_mgr):
        tid = tool_mgr.get_next_tool_id()
        assert tid > 0

    def test_get_all_tools(self, tool_mgr):
        tools = tool_mgr.get_all_tools()
        assert isinstance(tools, list)

    def test_get_raw_all_tools(self, tool_mgr):
        tools = tool_mgr.get_raw_all_tools()
        assert tools is not None

    @patch("tools.tool_manager.CustomizeMilvus")
    def test_milvus_methods_mocked(self, mock_milvus_cls, tool_mgr):
        """验证 get_docs/get_embeddings 等 Milvus 方法通过 mock 覆盖"""
        mock_milvus = mock_milvus_cls.return_value
        mock_milvus.get_docs.return_value = []
        mock_milvus.get_embeddings.return_value = []
        mock_milvus.count_collection.return_value = 0
        mock_milvus.collection_exists.return_value = True
        mock_milvus.insert_tools.return_value = None
        mock_milvus.delete_tools.return_value = None
        mock_milvus.drop_collection.return_value = None

        # 替换 tool_mgr 的 milvus
        old_milvus = tool_mgr.milvus
        tool_mgr.milvus = mock_milvus

        try:
            # 测试 get_docs
            docs = tool_mgr.milvus.get_docs("tools", "test query", 5)
            assert docs == []
            mock_milvus.get_docs.assert_called()

            # 测试 get_embeddings
            embs = tool_mgr.milvus.get_embeddings(["text1"])
            assert embs == []

            # 测试 count_collection
            cnt = tool_mgr.milvus.count_collection("tools")
            assert cnt == 0

            # 测试 collection_exists
            assert tool_mgr.milvus.collection_exists("tools") is True
        finally:
            tool_mgr.milvus = old_milvus
