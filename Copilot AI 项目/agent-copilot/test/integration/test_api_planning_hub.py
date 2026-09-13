"""集成测试 — 真实 MongoDB + Mock LLM 的 api_planning_hub 核心流程测试"""

import os
import sys
import pytest
import json
from unittest.mock import MagicMock, patch, PropertyMock

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

os.environ["mongo_port"] = "27112"
os.environ["mongo_host"] = "127.0.0.1"
os.environ["milvus_uri"] = "http://127.0.0.1:19530"
os.environ["local_mode"] = "0"


@pytest.fixture(scope="module")
def planning_hub():
    """用真实 MongoDB + mock LLM 创建 ApiPlanningHub"""
    # Mock 所有 LLM 调用
    with patch("models.llm.LargeLanguageModel") as mock_llm_cls, \
         patch("tasks.generate_task_hub.LargeLanguageModel") as mock_llm2, \
         patch("models.llm.OpenAI"):
        mock_llm = mock_llm_cls.return_value
        mock_llm.chat_completions.return_value = "mock response"
        mock_llm2.return_value = mock_llm

        from apis.api_planning_hub import ApiPlanningHub
        from tasks.task_manager import TaskManager
        from tools.tool_manager import ToolManager

        # 先清理
        try:
            tm = ToolManager("127.0.0.1", "tools", 27112, "http://127.0.0.1:19530", "tool_db")
            tm.delete_all_tools()
        except Exception:
            pass

        hub = ApiPlanningHub(
            milvus_uri="http://127.0.0.1:19530",
            model_path="model",
            milvus_db_name="tool_db",
            model="deepseek-v3",
            temperature=0.01,
            top_p=0.01,
            mongo_host="127.0.0.1",
            mongo_db="tools",
            mongo_port=27112,
            topK=5,
            api_url="http://test.api",
            api_key="test-key",
            executor=None,
        )
        # 注入 mock LLM
        hub.llm = mock_llm
        hub.api_selection_hub.LargeLanguageModel = mock_llm
        hub.param_extraction_hub.LargeLanguageModel = mock_llm
        hub.tool_summary_hub.LargeLanguageModel = mock_llm
        hub.generate_task_hub.LargeLanguageModel = mock_llm

        yield hub, mock_llm

        # 清理
        try:
            hub.task_manager.mongoClient.drop_database("tools")
        except Exception:
            pass


class TestApiPlanningHubIntegration:
    """ApiPlanningHub 核心流程集成测试"""

    def test_init(self, planning_hub):
        hub, _ = planning_hub
        assert hub is not None
        assert hub.task_manager is not None
        assert hub.param_extraction_hub is not None
        assert hub.tool_summary_hub is not None

    def test_set_task_type(self, planning_hub):
        hub, _ = planning_hub
        task = hub.task_manager.create_task("测试查询")
        hub._set_task_type("测试查询", task.task_id, 1, "单工具任务")
        updated = hub.task_manager.get_task_by_id(task.task_id)
        assert updated is not None
        assert updated.task_type == 1

    def test_update_task_curr_desc(self, planning_hub):
        hub, _ = planning_hub
        task = hub.task_manager.create_task("测试")
        hub._update_task_curr_desc(task.task_id, "新描述")
        updated = hub.task_manager.get_task_by_id(task.task_id)
        assert updated.curr_task_desc == "新描述"

    def test_update_task_node_edge_success(self, planning_hub):
        hub, mock_llm = planning_hub
        task = hub.task_manager.create_task("测试查询")
        mock_llm.chat_completions.return_value = "摘要结果"

        result = {
            "code": 200,
            "result": "API调用成功",
            "tool": "测试工具",
            "missing_param": [],
            "param": {"key": "value"},
            "query": "子任务描述",
            "task_description": "子任务描述",
        }
        hub._update_task_node_edge(task, result, "处理完成", is_end=True)
        updated = hub.task_manager.get_task_by_id(task.task_id)
        assert updated is not None
        assert len(updated.nodes) == 1

    def test_update_task_node_edge_error_code(self, planning_hub):
        hub, _ = planning_hub
        task = hub.task_manager.create_task("错误查询")

        result = {
            "code": 404,
            "result": "error",
            "tool": "异常工具",
            "missing_param": [],
            "param": {},
            "query": "错误任务",
            "task_description": "错误",
        }
        hub._update_task_node_edge(task, result, "处理失败")
        updated = hub.task_manager.get_task_by_id(task.task_id)
        assert updated.status == -1  # FINISH

    def test_not_loop_validate_normal(self, planning_hub):
        hub, _ = planning_hub
        from conftest import MockTask
        task = MockTask(nodes=[
            {"label": "toolA", "result": "r1", "params": "{}"},
        ])
        cur_result = {"tool": "toolB", "result": "r2"}
        assert hub._not_loop_validate(task, cur_result) is True

    def test_supplement_parameters(self, planning_hub):
        hub, mock_llm = planning_hub
        mock_llm.chat_completions.return_value = "Action: None"
        result = hub._supplement_parameters("测试查询", "supplierId")
        assert result == (None, None, None)

    def test_process_single_api_invoke_success(self, planning_hub):
        hub, mock_llm = planning_hub
        from conftest import make_tool, make_param
        mock_llm.chat_completions.return_value = "摘要"

        task = hub.task_manager.create_task("测试")
        tool = make_tool("testTool", [make_param("p1", "string")])
        tool.api_url = "http://localhost:8080"
        tool.path = "/api/test"
        tool.method = "GET"
        tool.operationId = "testOp"
        tool.name_for_human = "测试工具"

        with patch.object(hub.tool_use_hub, "tool_use") as mock_use:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"result":"ok"}'
            mock_use.return_value = mock_resp

            result = hub._process_single_api_invoke("查询", task, tool, {"p1": "v1"})
            assert result["code"] == 200

    def test_process_single_api_invoke_failure(self, planning_hub):
        hub, _ = planning_hub
        from conftest import make_tool, make_param

        task = hub.task_manager.create_task("测试")
        tool = make_tool("testTool", [make_param("p1", "string")])
        tool.api_url = "http://localhost:8080"
        tool.path = "/api/test"
        tool.method = "GET"
        tool.operationId = "testOp"

        with patch.object(hub.tool_use_hub, "tool_use") as mock_use:
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_resp.text = ''
            mock_use.return_value = mock_resp

            result = hub._process_single_api_invoke("查询", task, tool, {"p1": "v1"})
            assert result["code"] == 404

    def test_get_summary_from_nodes(self, planning_hub):
        hub, _ = planning_hub
        from conftest import MockTask
        task = MockTask(nodes=[
            {"label": "tool1", "task_description": "d1", "result": "r1"},
            {"label": "tool2", "task_description": "d2", "result": "r2"},
        ])
        context = hub._get_summary_from_nodes(task)
        assert len(context) == 2
        assert context[0]["tool"] == "tool1"

    def test_recognize_human_intent_confirm(self, planning_hub):
        hub, _ = planning_hub
        mock_tool = MagicMock()
        mock_tool.name_for_human = "test"
        result = hub._recognize_human_intent("立即执行", mock_tool, {})
        assert result["intent"] == "confirm"

    def test_recognize_human_intent_abort(self, planning_hub):
        hub, _ = planning_hub
        mock_tool = MagicMock()
        mock_tool.name_for_human = "test"
        result = hub._recognize_human_intent("不执行", mock_tool, {})
        assert result["intent"] == "abort"

    def test_generate_output(self, planning_hub):
        hub, mock_llm = planning_hub
        mock_llm.chat_completions.return_value = "润色后的结果"
        result = hub.generate_output("原始文本")
        assert result == "润色后的结果"
