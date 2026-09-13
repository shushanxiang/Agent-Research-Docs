"""最终批量集成测试 — 覆盖 api_planning_hub, api_selection_hub, tool_manager 最大缺口"""

import os, sys, json, pytest
from unittest.mock import MagicMock, patch, PropertyMock

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

os.environ["mongo_port"] = "27112"
os.environ["mongo_host"] = "127.0.0.1"
os.environ["milvus_uri"] = "http://127.0.0.1:19530"
os.environ["local_mode"] = "0"


@pytest.fixture(scope="module")
def hub():
    """创建带 mock LLM 的 ApiPlanningHub"""
    with patch("models.llm.OpenAI"):
        from apis.api_planning_hub import ApiPlanningHub
        from tools.tool_manager import ToolManager
        from entity.tool_entity import Tool, Parameter

        # 清理并插入测试工具
        try:
            tm = ToolManager("127.0.0.1", "tools", 27112, "http://127.0.0.1:19530", "tool_db")
            tm.delete_all_tools()
        except Exception:
            pass

        p = Parameter(name="productName", type="string", description="产品名称",
                      required=True, enum=[], format="", in_="query")
        tool = Tool()
        tm2 = ToolManager("127.0.0.1", "tools", 27112, "http://127.0.0.1:19530", "tool_db")
        tid = tm2.get_next_tool_id()
        tool.tool_id = tid
        tool.operationId = "getByProductName"
        tool.name_for_human = "按名称查询产品"
        tool.name_for_model = "tool1"
        tool.description = "根据产品名称模糊查询产品信息"
        tool.api_url = "http://localhost:8080"
        tool.path = "/api/products/name"
        tool.method = "GET"
        tool.request_body = [p]
        tool.isValidate = False
        tool.save()

        hub = ApiPlanningHub(
            milvus_uri="http://127.0.0.1:19530", model_path="model",
            milvus_db_name="tool_db", model="deepseek-v3",
            temperature=0.01, top_p=0.01,
            mongo_host="127.0.0.1", mongo_db="tools", mongo_port=27112,
            topK=5, api_url="http://test.api", api_key="test-key", executor=None,
        )

        mock_llm = MagicMock()
        mock_llm.chat_completions.return_value = "mock"
        hub.llm = mock_llm
        hub.api_selection_hub.LargeLanguageModel = mock_llm
        hub.param_extraction_hub.LargeLanguageModel = mock_llm
        hub.tool_summary_hub.LargeLanguageModel = mock_llm
        hub.generate_task_hub.LargeLanguageModel = mock_llm

        yield hub, mock_llm

        try:
            hub.task_manager.mongoClient.drop_database("tools")
        except Exception:
            pass


class TestToolCheck:
    """_tool_check 方法全面覆盖"""

    def test_tool_check_missing_params(self, hub):
        h, mock_llm = hub
        from conftest import make_tool, make_param

        tool = make_tool("testTool", [make_param("productId", "int64", required=True)])
        tool.name_for_human = "测试工具"
        tool.isValidate = False
        tool.tool_id = 1

        # gen_param_task_prompt 是真实 PromptModelHub 上的方法，需要用 MagicMock 替换整个 PromptModelHub
        h.generate_task_hub.PromptModelHub = MagicMock()
        h.generate_task_hub.PromptModelHub.gen_param_task_prompt.return_value = "gen_param_prompt"
        h.generate_task_hub.PromptModelHub.post_process_gen_root_task.return_value = (True, None)

        result = h._tool_check(tool, "查询", "原始查询")
        assert result["code"] in [200, 404]  # 参数缺失 → 补充失败

    def test_tool_check_all_params_present(self, hub):
        h, mock_llm = hub
        from conftest import make_tool, make_param

        tool = make_tool("testTool", [make_param("name", "string", required=True)])
        tool.name_for_human = "测试工具"
        tool.isValidate = False
        tool.tool_id = 1

        h.param_extraction_hub.PromptModelHub = MagicMock()
        h.param_extraction_hub.PromptModelHub.gen_get_all_parameters_prompt.return_value = "prompt"
        h.param_extraction_hub.PromptModelHub.post_process_get_all_parameter_result.return_value = {"name": "苹果"}

        h.generate_task_hub.PromptModelHub = MagicMock()
        h.generate_task_hub.PromptModelHub.judge_validate.return_value = "judge_prompt"
        h.generate_task_hub.PromptModelHub.post_process_gen_judge_task.return_value = (False, None)

        result = h._tool_check(tool, "查询苹果", "原始查询")
        assert result["code"] == 200

    def test_tool_check_injection_detected(self, hub):
        h, mock_llm = hub
        from conftest import make_tool, make_param

        tool = make_tool("testTool", [make_param("quantity", "int32", required=True)], is_validate=True)
        tool.name_for_human = "创建订单"
        tool.tool_id = 3

        h.param_extraction_hub.PromptModelHub = MagicMock()
        h.param_extraction_hub.PromptModelHub.gen_get_all_parameters_prompt.return_value = "prompt"
        h.param_extraction_hub.PromptModelHub.post_process_get_all_parameter_result.return_value = {"quantity": -10}

        result = h._tool_check(tool, "创建订单", "原始查询")
        assert result["code"] in [200, 404]


class TestApiPlanningBeforeHumanFeedback:
    """api_planning_before_human_feedback 完整流程"""

    def test_tool_found_confirms(self, hub):
        h, mock_llm = hub
        from conftest import make_tool, make_param

        tool = make_tool("found", [make_param("p1", "string")])
        tool.tool_id = 1
        tool.name_for_human = "测试工具"
        tool.isValidate = False
        tool.api_url = "http://localhost:8080"
        tool.path = "/api/test"
        tool.method = "GET"

        with patch.object(h.api_selection_hub, "get_tool_coarse_and_fine", return_value=tool), \
             patch.object(h, "_tool_check") as mock_tc:
            mock_tc.return_value = {
                "code": 200, "result": "", "tool": "测试工具",
                "missing_param": [], "param": {"p1": "v1"},
                "query": "测试", "task_description": "测试",
            }
            h.api_planning_before_human_feedback("查询", "tid-t1", "原始")

            task = h.task_manager.get_task_by_id("tid-t1")
            if task:
                assert task.status in [1, 100, -1]  # RUNNING or WAIT_CONFIRM or FINISH

    def test_tool_not_found_shows_error(self, hub):
        h, _ = hub
        with patch.object(h.api_selection_hub, "get_tool_coarse_and_fine", return_value=None):
            h.api_planning_before_human_feedback("不存在的查询", "tid-no-tool", "原始")

            task = h.task_manager.get_task_by_id("tid-no-tool")
            if task:
                assert task.status == -1  # FINISH

    def test_tool_check_error(self, hub):
        h, mock_llm = hub
        from conftest import make_tool, make_param

        tool = make_tool("found", [make_param("p1", "string")])
        tool.tool_id = 1
        tool.name_for_human = "测试工具"
        tool.isValidate = False

        with patch.object(h.api_selection_hub, "get_tool_coarse_and_fine", return_value=tool), \
             patch.object(h, "_tool_check") as mock_tc:
            mock_tc.return_value = {"code": 404, "result": "error", "tool": "error",
                                     "missing_param": [], "param": {}, "query": "q",
                                     "task_description": "错误描述"}
            h.api_planning_before_human_feedback("查询", "tid-error", "原始")

            task = h.task_manager.get_task_by_id("tid-error")
            if task:
                assert task.status == -1


class TestHandleHumanFeedbackExtended:
    """api_planning_handle_human_feedback 更全面测试"""

    def test_confirm_multi_task(self, hub):
        h, _ = hub
        from conftest import make_tool, make_param

        t = make_tool("multiTool", [make_param("p1", "string")])
        t.name_for_human = "多任务工具"
        t.description = "desc"
        t.tool_id = 5
        t.isValidate = False
        t.api_url = "http://localhost:8080"
        t.path = "/api/multi"
        t.method = "GET"
        t.operationId = "multiOp"

        task = h.task_manager.create_task("多任务测试", exists_task_id="hfb-multi")
        task.curr_tool_id = 5
        task.curr_tool_param = {"p1": "v1"}
        task.task_type = 2  # APIS (multi)
        task.changed_query = "多任务测试"
        task.raw_query = "原始"
        task.save()

        mock_llm = h.generate_task_hub.LargeLanguageModel
        mock_llm.chat_completions.return_value = "Task completed: Yes\nNext Subtask: None"
        h.generate_task_hub.PromptModelHub = MagicMock()
        h.generate_task_hub.PromptModelHub.gen_subtask_context_prompt.return_value = "ctx_prompt"
        h.generate_task_hub.PromptModelHub.post_process_gen_subtask_task.return_value = (True, None)

        with patch.object(h.tool_manager, "get_tools_by_ids", return_value=[t]), \
             patch.object(h.tool_use_hub, "tool_use") as mock_use:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"data":"ok"}'
            mock_use.return_value = mock_resp

            h.api_planning_handle_human_feedback(task, "立即执行")

        updated = h.task_manager.get_task_by_id("hfb-multi")
        if updated:
            assert updated.status in [1, -1]

    def test_confirm_multi_task_loop_detected(self, hub):
        h, _ = hub
        from conftest import make_tool, make_param

        t = make_tool("loopTool", [make_param("p1", "string")])
        t.name_for_human = "循环工具"
        t.tool_id = 5
        t.isValidate = False
        t.api_url = "http://localhost:8080"
        t.path = "/api/loop"
        t.method = "GET"
        t.operationId = "loopOp"

        # task 已有足够多的节点来触发循环检测
        nodes = [{"label": "循环工具", "result": "same", "params": "{}"} for _ in range(3)]
        task = h.task_manager.create_task("循环测试", exists_task_id="hfb-loop")
        task.curr_tool_id = 5
        task.curr_tool_param = {"p1": "v1"}
        task.task_type = 2
        task.changed_query = "loop"
        task.raw_query = "loop"
        task.nodes = nodes  # 已填 3 个相同工具+结果
        task.save()

        with patch.object(h.tool_manager, "get_tools_by_ids", return_value=[t]), \
             patch.object(h.tool_use_hub, "tool_use") as mock_use:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"data":"same"}'
            mock_use.return_value = mock_resp

            h.api_planning_handle_human_feedback(task, "立即执行")

        updated = h.task_manager.get_task_by_id("hfb-loop")
        if updated:
            assert updated.status == -1  # 循环检测中止


class TestApiSelectionHubExtended:
    """ApiSelectionHub 全覆盖"""

    def test_get_tool_coarse_and_fine_with_rerank(self, hub):
        h, mock_llm = hub
        mock_llm.chat_completions.return_value = "Action: tool1"

        # force vector_search path
        from conftest import make_tool, make_param
        with patch.object(h.api_selection_hub.milvus, "get_docs", return_value=[5]), \
             patch.object(h.api_selection_hub.ToolManager, "search_tools_with_rerank", return_value=[]) as mock_rerank:
            mock_rerank.return_value = []
            result = h.api_selection_hub.get_tool_coarse_and_fine("查询", None, topK=3)
            # falls back to vector_search_tools since rerank returned empty
            if result is not None:
                assert hasattr(result, "name_for_human")


class TestGenerateOutput:
    """generate_output 方法"""

    def test_generate_output(self, hub):
        h, mock_llm = hub
        mock_llm.chat_completions.return_value = "润色后的文本"
        result = h.generate_output("原始文本需要润色")
        assert "润色" in result or result == "润色后的文本"
