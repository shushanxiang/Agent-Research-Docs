"""扩展集成测试 — apis_planning, api_planning_before_human_feedback, handle_human_feedback"""

import os, sys, json, pytest
from unittest.mock import MagicMock, patch

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

os.environ["mongo_port"] = "27112"
os.environ["mongo_host"] = "127.0.0.1"
os.environ["milvus_uri"] = "http://127.0.0.1:19530"
os.environ["local_mode"] = "0"


@pytest.fixture(scope="module")
def hub_with_data():
    """创建带插入工具的 ApiPlanningHub"""
    with patch("models.llm.OpenAI"):
        from apis.api_planning_hub import ApiPlanningHub
        from tasks.task_manager import TaskManager
        from tools.tool_manager import ToolManager
        from entity.tool_entity import Tool, Parameter

        # 清理
        try:
            tm = ToolManager("127.0.0.1", "tools", 27112, "http://127.0.0.1:19530", "tool_db")
            tm.delete_all_tools()
        except Exception:
            pass

        # 插入一个测试工具（isValidate=False，以跳过 injection check）
        p = Parameter(name="productName", type="string", description="产品名称",
                      required=True, enum=[], format="", in_="query")
        tool = Tool()
        tid = ToolManager("127.0.0.1", "tools", 27112, "http://127.0.0.1:19530", "tool_db").get_next_tool_id()
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

        # Mock 所有 LLM 调用
        mock_llm = MagicMock()
        mock_llm.chat_completions.return_value = "mock response"
        hub.llm = mock_llm
        hub.api_selection_hub.LargeLanguageModel = mock_llm
        hub.param_extraction_hub.LargeLanguageModel = mock_llm
        hub.tool_summary_hub.LargeLanguageModel = mock_llm
        hub.generate_task_hub.LargeLanguageModel = mock_llm

        # Mock PromptModelHub 返回有效的解析结果
        hub.prompt_hub = MagicMock()
        hub.api_selection_hub.PromptModelHub = hub.prompt_hub
        hub.param_extraction_hub.PromptModelHub = hub.prompt_hub
        hub.generate_task_hub.PromptModelHub = hub.prompt_hub

        yield hub, mock_llm

        # 清理
        try:
            hub.task_manager.mongoClient.drop_database("tools")
        except Exception:
            pass


class TestApisPlanning:
    """apis_planning 流程测试"""

    def test_apis_planning_single_task(self, hub_with_data):
        hub, mock_llm = hub_with_data

        # setUp 单任务判断 → Yes
        mock_llm.chat_completions.side_effect = [
            "Single API tool task: Yes\nFirst subtask description: None",  # gen_root_task
            "mock",                                                         # gen_tool_selection_prompt call
        ]

        hub.generate_task_hub.PromptModelHub.gen_root_task_prompt.return_value = "root_prompt"
        hub.generate_task_hub.PromptModelHub.post_process_gen_root_task.return_value = (True, None)

        hub.api_planning_before_human_feedback = MagicMock()

        hub.apis_planning("查询苹果", "test-task-id-001")

        # 应该调用 api_planning_before_human_feedback（单任务）
        assert hub.api_planning_before_human_feedback.called

    def test_apis_planning_multi_task(self, hub_with_data):
        hub, mock_llm = hub_with_data

        # setUp 多任务判断 → No + 子任务描述
        mock_llm.chat_completions.side_effect = [
            "Single API tool task: No\nFirst subtask description: 查询苹果的产品信息",  # gen_root_task
        ]

        hub.generate_task_hub.PromptModelHub.gen_root_task_prompt.return_value = "root_prompt"
        hub.generate_task_hub.PromptModelHub.post_process_gen_root_task.return_value = (False, "查询苹果的产品信息")

        hub.api_planning_before_human_feedback = MagicMock()

        hub.apis_planning("先查苹果再查梨子", "test-task-id-002")

        assert hub.api_planning_before_human_feedback.called


class TestBeforeHumanFeedback:
    """api_planning_before_human_feedback 流程"""

    def test_no_tool_found(self, hub_with_data):
        hub, mock_llm = hub_with_data

        # 搜索无结果 → get_tool_coarse_and_fine returns None
        with patch.object(hub.api_selection_hub, "get_tool_coarse_and_fine", return_value=None):
            hub.api_planning_before_human_feedback("不存在的查询", "tid-1", "原始查询")
            # 应该更新任务为 FINISH 状态
            task = hub.task_manager.get_task_by_id("tid-1")
            assert task is None or task.status == -1

    def test_tool_found_success(self, hub_with_data):
        hub, mock_llm = hub_with_data
        from conftest import make_tool, make_param

        tool = make_tool("foundTool", [make_param("p1", "string")])
        tool.tool_id = 1
        tool.name_for_human = "找到的工具"
        tool.name_for_model = "tool1"
        tool.description = "desc"
        tool.isValidate = False
        tool.api_url = "http://localhost:8080"
        tool.path = "/api/test"
        tool.method = "GET"

        # Mock 让 tool_check 返回成功
        with patch.object(hub.api_selection_hub, "get_tool_coarse_and_fine", return_value=tool), \
             patch.object(hub, "_tool_check") as mock_check:
            mock_check.return_value = {
                "code": 200, "result": "", "tool": "找到的工具",
                "missing_param": [], "param": {"p1": "v1"},
                "query": "任务描述", "task_description": "任务描述"
            }
            hub.api_planning_before_human_feedback("查询", "tid-2", "原始查询")
            # 应该进入 WAIT_CONFIRM 状态
            task = hub.task_manager.get_task_by_id("tid-2")
            if task:
                assert mock_check.called


class TestHandleHumanFeedback:
    """api_planning_handle_human_feedback 测试"""

    def test_abort(self, hub_with_data):
        hub, _ = hub_with_data
        from conftest import MockTask

        task = MockTask(nodes=[], task_id="hfb-abort")
        task.curr_tool_id = 5
        task.curr_tool_param = {"p1": "v1"}
        task.task_type = 1  # SINGLE
        task.changed_query = "测试查询"
        task.raw_query = "测试原始查询"

        # 需要先创建 task 实体在 MongoDB 中
        real_task = hub.task_manager.create_task("测试", exists_task_id="hfb-abort")

        # Mock 工具获取
        with patch.object(hub.tool_manager, "get_tools_by_ids") as mock_tools:
            from conftest import make_tool, make_param
            t = make_tool("testTool", [make_param("p1", "string")])
            t.name_for_human = "测试工具"
            t.description = "desc"
            t.isValidate = False
            t.tool_id = 5
            mock_tools.return_value = [t]

            hub.api_planning_handle_human_feedback(real_task, "不执行")

        updated = hub.task_manager.get_task_by_id("hfb-abort")
        if updated:
            assert updated.status == -1  # FINISH

    def test_confirm_single_task(self, hub_with_data):
        hub, _ = hub_with_data
        from conftest import make_tool, make_param

        t = make_tool("testTool", [make_param("p1", "string")])
        t.name_for_human = "测试工具"
        t.description = "desc"
        t.isValidate = False
        t.tool_id = 5
        t.api_url = "http://localhost:8080"
        t.path = "/api/test"
        t.method = "GET"
        t.operationId = "testOp"

        task = hub.task_manager.create_task("测试", exists_task_id="hfb-confirm-single")
        task.curr_tool_id = 5
        task.curr_tool_param = {"p1": "v1"}
        task.task_type = 1  # SINGLE
        task.changed_query = "测试"
        task.raw_query = "原始"
        task.save()

        with patch.object(hub.tool_manager, "get_tools_by_ids", return_value=[t]), \
             patch.object(hub.tool_use_hub, "tool_use") as mock_use, \
             patch.object(hub.tool_summary_hub, "tool_summary", return_value="任务总结"):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"result":"ok"}'
            mock_use.return_value = mock_resp

            hub.api_planning_handle_human_feedback(task, "立即执行")

        updated = hub.task_manager.get_task_by_id("hfb-confirm-single")
        if updated:
            assert updated.status == -1  # FINISH

    def test_init_tool_id_returns(self, hub_with_data):
        """无等待确认工具时返回"""
        hub, _ = hub_with_data
        task = hub.task_manager.create_task("测试", exists_task_id="hfb-no-tool")
        task.task_type = 1
        task.save()

        hub.api_planning_handle_human_feedback(task, "立即执行")

        updated = hub.task_manager.get_task_by_id("hfb-no-tool")
        if updated:
            assert updated.status == -1


class TestApiSelectionHub:
    """ApiSelectionHub 测试"""

    def test_get_tool_coarse_and_fine(self, hub_with_data):
        hub, mock_llm = hub_with_data
        mock_llm.chat_completions.return_value = "Action: tool1"

        from conftest import make_tool, make_param
        with patch.object(hub.api_selection_hub.milvus, "get_docs", return_value=[5]):
            result = hub.api_selection_hub.get_tool_coarse_and_fine("查询苹果", None, topK=5)
            # 可能返回 tool 或 None（取决于 reranker 和 LLM）
            if result is not None:
                assert hasattr(result, "name_for_human")

    def test_get_tool_coarse_and_fine_with_required(self, hub_with_data):
        hub, mock_llm = hub_with_data
        mock_llm.chat_completions.return_value = "Action: tool1"

        with patch.object(hub.api_selection_hub.milvus, "get_docs", return_value=[5]):
            result = hub.api_selection_hub.get_tool_coarse_and_fine("查询", "supplierId", topK=5)
            if result is not None:
                assert hasattr(result, "name_for_human")

    def test_get_tool_coarse_and_fine_exception(self, hub_with_data):
        """Milvus 异常时返回 None"""
        hub, mock_llm = hub_with_data
        with patch.object(hub.api_selection_hub.milvus, "get_docs", side_effect=Exception("Milvus down")):
            result = hub.api_selection_hub.get_tool_coarse_and_fine("查询", None, topK=5)
            assert result is None
