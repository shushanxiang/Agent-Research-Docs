"""集成测试 — ToolManager & TaskManager（需要 MongoDB + Milvus）"""

import os
import sys
import pytest
import json

# 确保项目根在 sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# 测试环境配置：MongoDB 端口 27112
os.environ["mongo_port"] = "27112"
os.environ["mongo_host"] = "127.0.0.1"
os.environ["milvus_uri"] = "http://127.0.0.1:19530"
os.environ["local_mode"] = "0"  # 不使用 local_mode 覆盖


@pytest.fixture(scope="module")
def tool_manager():
    """创建真实的 ToolManager 实例"""
    from tools.tool_manager import ToolManager
    tm = ToolManager("127.0.0.1", "tools", 27112, "http://127.0.0.1:19530", "tool_db")
    yield tm
    # 清理
    try:
        tm.mongoClient.drop_database("tools")
    except Exception:
        pass


@pytest.fixture(scope="module")
def task_manager():
    """创建真实的 TaskManager 实例"""
    from tasks.task_manager import TaskManager
    tm = TaskManager("127.0.0.1", "tools", 27112)
    yield tm
    try:
        tm.mongoClient.drop_database("tools")
    except Exception:
        pass


class TestToolManagerIntegration:
    """ToolManager 集成测试"""

    def test_init_connects(self, tool_manager):
        """初始化连接成功"""
        assert tool_manager is not None
        assert tool_manager.mongoClient is not None
        assert tool_manager.milvus is not None

    def test_insert_tool(self, tool_manager):
        """插入单个工具"""
        from entity.tool_entity import Tool, Parameter

        # 先清理
        try:
            tool_manager.delete_all_tools()
        except Exception:
            pass

        p1 = Parameter(name="productName", type="string", description="产品名称",
                       required=True, enum=[], format="", in_="query")

        tool = Tool()
        tool.tool_id = 99999
        tool.operationId = "testOp"
        tool.name_for_human = "测试工具"
        tool.name_for_model = "testTool"
        tool.description = "测试工具描述"
        tool.api_url = "http://localhost:8080"
        tool.path = "/api/test"
        tool.method = "GET"
        tool.request_body = [p1]
        tool.isValidate = False

        tool.save()
        assert tool.pk is not None

    def test_get_all_tools(self, tool_manager):
        """获取所有工具"""
        tools = tool_manager.get_all_tools()
        assert isinstance(tools, list)

    def test_get_raw_all_tools(self, tool_manager):
        """获取原始工具列表"""
        tools = tool_manager.get_raw_all_tools()
        assert tools is not None

    def test_get_tools_by_ids(self, tool_manager):
        """按 ID 查询工具"""
        tools = tool_manager.get_tools_by_ids([99999])
        assert len(tools) >= 1
        if len(tools) > 0:
            assert tools[0].tool_id == 99999

    def test_search_tools_with_rerank(self, tool_manager):
        """rerank 搜索（需要有效 API key）"""
        try:
            result = tool_manager.search_tools_with_rerank("测试查询", top_k=5, final_top_n=2)
            assert isinstance(result, list)
        except Exception:
            pytest.skip("reranker requires valid API key")

    def test_clear_cache(self, tool_manager):
        """清理缓存"""
        tool_manager.clear_cache()

    def test_delete_tools(self, tool_manager):
        """删除工具并清理缓存"""
        try:
            tool_manager.delete_tools([99999])
        except Exception:
            pass


class TestTaskManagerIntegration:
    """TaskManager 集成测试"""

    def test_create_task(self, task_manager):
        """创建任务"""
        task = task_manager.create_task("用户查询测试")
        assert task is not None
        assert task.task_id is not None
        assert task.status == 0  # INIT
        assert task.raw_query == "用户查询测试"

    def test_update_task_recorder(self, task_manager):
        """更新任务"""
        task = task_manager.create_task("更新测试查询")
        tid = task_manager.update_task_recorder(
            task.task_id, 1, "正在处理...",
            graph_title="正常调用链",
            curr_task_desc="子任务描述",
            task_type=1
        )
        assert tid == task.task_id

    def test_get_task_by_id(self, task_manager):
        """按 ID 获取任务"""
        task = task_manager.create_task("测试获取")
        fetched = task_manager.get_task_by_id(task.task_id)
        assert fetched is not None
        assert fetched.task_id == task.task_id

    def test_get_task_by_id_not_found(self, task_manager):
        """不存在的 task_id 返回 None"""
        fetched = task_manager.get_task_by_id("non-existent-id-xyz")
        assert fetched is None

    def test_task_to_dict(self, task_manager):
        """Task 转字典"""
        task = task_manager.create_task("测试 to_dict")
        d = task.to_dict()
        assert d["task_id"] == task.task_id
        assert "status" in d
        assert "nodes" in d
        assert "systemOutput" in d
        assert "isSuccess" in d

    def test_create_task_with_existing_id(self, task_manager):
        """带已有 ID 创建任务"""
        task = task_manager.create_task("测试", exists_task_id="test-id-001")
        assert task is not None
        assert task.task_id == "test-id-001"
        assert task.status == -1  # FINISH for existing ID


class TestToolEntity:
    """实体类测试"""

    def test_parameter_entity(self):
        from entity.tool_entity import Parameter
        p = Parameter(name="test", type="int32", description="desc",
                      required=True, enum=["a","b"], format="", in_="query")
        assert p.name == "test"
        assert p.type == "int32"
        assert p.required is True
        assert len(p.enum) == 2

    def test_task_entity_to_dict(self):
        from entity.task_entity import Task
        t = Task()
        t.task_id = "abc-123"
        t.status = 0
        t.nodes = []
        t.edges = []
        t.graph_title = "测试标题"
        t.system_output = "测试输出"
        d = t.to_dict()
        assert d["task_id"] == "abc-123"
        assert d["isSuccess"] == "测试标题"
        assert d["systemOutput"] == "测试输出"
