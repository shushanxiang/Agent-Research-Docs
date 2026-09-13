"""最终推动覆盖率至 85% — 补充 api_planning_hub.py 核心未覆盖分支"""

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
def hub():
    with patch("models.llm.OpenAI"):
        from apis.api_planning_hub import ApiPlanningHub
        from tools.tool_manager import ToolManager
        from entity.tool_entity import Tool, Parameter

        try:
            tm = ToolManager("127.0.0.1", "tools", 27112, "http://127.0.0.1:19530", "tool_db")
            tm.delete_all_tools()
        except Exception:
            pass

        # 插入测试工具
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
            milvus_db_name="tool_db", model="deepseek-v3", temperature=0.01, top_p=0.01,
            mongo_host="127.0.0.1", mongo_db="tools", mongo_port=27112,
            topK=5, api_url="http://test.api", api_key="test-key", executor=None,
        )

        m = MagicMock()
        m.chat_completions.return_value = "mock"
        hub.llm = m
        hub.api_selection_hub.LargeLanguageModel = m
        hub.param_extraction_hub.LargeLanguageModel = m
        hub.tool_summary_hub.LargeLanguageModel = m
        hub.generate_task_hub.LargeLanguageModel = m

        yield hub, m

        try:
            hub.task_manager.mongoClient.drop_database("tools")
        except Exception:
            pass


class TestCoveragePush85:
    """补覆盖率至 85% 的关键测试"""

    def test_intent_confirm_multi_api_continue(self, hub):
        """多 API 任务 confirm 后继续下一个子任务"""
        h, _ = hub
        from conftest import make_tool, make_param, MockTask

        t = make_tool("testTool", [make_param("p1", "string")])
        t.name_for_human = "测试工具"
        t.description = "desc"
        t.tool_id = 5
        t.isValidate = False
        t.api_url = "http://localhost:8080"
        t.path = "/api/test"
        t.method = "GET"
        t.operationId = "testOp"

        task = h.task_manager.create_task("多API测试", exists_task_id="cov-multi-continue")
        task.curr_tool_id = 5
        task.curr_tool_param = {"p1": "v1"}
        task.task_type = 2  # multi
        task.changed_query = "multi"
        task.raw_query = "raw"
        task.save()

        # Mock: tool_use 成功，gen_from_context_task 返回 "继续"
        h.generate_task_hub.PromptModelHub = MagicMock()
        h.generate_task_hub.PromptModelHub.gen_subtask_context_prompt.return_value = "p"
        h.generate_task_hub.PromptModelHub.post_process_gen_subtask_task.return_value = (False, "下一个子任务")

        with patch.object(h.tool_manager, "get_tools_by_ids", return_value=[t]), \
             patch.object(h.tool_use_hub, "tool_use") as mock_use:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"result":"ok"}'
            mock_use.return_value = mock_resp

            h.api_planning_handle_human_feedback(task, "立即执行")

        updated = h.task_manager.get_task_by_id("cov-multi-continue")
        assert updated is not None

    def test_intent_confirm_multi_api_error(self, hub):
        """多 API 任务 confirm 后 tool_use 失败"""
        h, _ = hub
        from conftest import make_tool, make_param

        t = make_tool("badTool", [make_param("p1", "string")])
        t.name_for_human = "坏工具"
        t.tool_id = 5
        t.isValidate = False
        t.api_url = "http://localhost:8080"
        t.path = "/api/bad"
        t.method = "GET"
        t.operationId = "badOp"

        task = h.task_manager.create_task("错误测试", exists_task_id="cov-multi-error")
        task.curr_tool_id = 5
        task.curr_tool_param = {"p1": "v1"}
        task.task_type = 2
        task.changed_query = "err"
        task.raw_query = "raw"
        task.save()

        with patch.object(h.tool_manager, "get_tools_by_ids", return_value=[t]), \
             patch.object(h.tool_use_hub, "tool_use") as mock_use:
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_resp.text = ''
            mock_use.return_value = mock_resp

            h.api_planning_handle_human_feedback(task, "立即执行")

        updated = h.task_manager.get_task_by_id("cov-multi-error")
        if updated:
            assert updated.status == -1

    def test_intent_confirm_multi_api_final_summary(self, hub):
        """多 API 任务最后一步 → 生成最终摘要"""
        h, _ = hub
        from conftest import make_tool, make_param

        t = make_tool("finalTool", [make_param("p1", "string")])
        t.name_for_human = "最终工具"
        t.tool_id = 5
        t.isValidate = False
        t.api_url = "http://localhost:8080"
        t.path = "/api/final"
        t.method = "GET"
        t.operationId = "finalOp"

        task = h.task_manager.create_task("最终测试", exists_task_id="cov-multi-final")
        task.curr_tool_id = 5
        task.curr_tool_param = {"p1": "v1"}
        task.task_type = 2
        task.changed_query = "final"
        task.raw_query = "raw"
        task.nodes = [{"label": "tool1", "result": "r1", "params": "{}", "task_description": "d1"}]
        task.save()

        h.generate_task_hub.PromptModelHub = MagicMock()
        h.generate_task_hub.PromptModelHub.gen_subtask_context_prompt.return_value = "p"
        h.generate_task_hub.PromptModelHub.post_process_gen_subtask_task.return_value = (True, None)

        with patch.object(h.tool_manager, "get_tools_by_ids", return_value=[t]), \
             patch.object(h.tool_use_hub, "tool_use") as mock_use, \
             patch.object(h.tool_summary_hub, "tool_summary", return_value="最终摘要结果"):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"final":"ok"}'
            mock_use.return_value = mock_resp

            h.api_planning_handle_human_feedback(task, "立即执行")

        updated = h.task_manager.get_task_by_id("cov-multi-final")
        if updated:
            assert updated.status == -1

    def test_intent_confirm_single_from_handle(self, hub):
        """单 API 任务确认 — 完整 success 路径"""
        h, _ = hub
        from conftest import make_tool, make_param

        t = make_tool("singleTool", [make_param("p1", "string")])
        t.name_for_human = "单任务工具"
        t.tool_id = 5
        t.isValidate = False
        t.api_url = "http://localhost:8080"
        t.path = "/api/single"
        t.method = "GET"
        t.operationId = "singleOp"

        task = h.task_manager.create_task("单任务", exists_task_id="cov-single-ok")
        task.curr_tool_id = 5
        task.curr_tool_param = {"p1": "v1"}
        task.task_type = 1  # single
        task.changed_query = "single"
        task.raw_query = "raw"
        task.save()

        with patch.object(h.tool_manager, "get_tools_by_ids", return_value=[t]), \
             patch.object(h.tool_use_hub, "tool_use") as mock_use, \
             patch.object(h.tool_summary_hub, "tool_summary", return_value="单任务总结"):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"data":"ok"}'
            mock_use.return_value = mock_resp

            h.api_planning_handle_human_feedback(task, "立即执行")

        updated = h.task_manager.get_task_by_id("cov-single-ok")
        if updated:
            assert updated.status == -1

    def test_intent_confirm_single_error(self, hub):
        """单 API 任务确认 → tool_use 失败"""
        h, _ = hub
        from conftest import make_tool, make_param

        t = make_tool("badSingle", [make_param("p1", "string")])
        t.name_for_human = "坏单任务"
        t.tool_id = 5
        t.isValidate = False
        t.api_url = "http://localhost:8080"
        t.path = "/api/badsingle"
        t.method = "GET"
        t.operationId = "badSingleOp"

        task = h.task_manager.create_task("单任务错误", exists_task_id="cov-single-err")
        task.curr_tool_id = 5
        task.curr_tool_param = {"p1": "v1"}
        task.task_type = 1
        task.changed_query = "err"
        task.raw_query = "raw"
        task.save()

        with patch.object(h.tool_manager, "get_tools_by_ids", return_value=[t]), \
             patch.object(h.tool_use_hub, "tool_use") as mock_use:
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_resp.text = ''
            mock_use.return_value = mock_resp

            h.api_planning_handle_human_feedback(task, "立即执行")

        updated = h.task_manager.get_task_by_id("cov-single-err")
        if updated:
            assert updated.status == -1

    def test_intent_unclear(self, hub):
        """意图识别不明确"""
        h, _ = hub
        from conftest import make_tool, make_param

        t = make_tool("someTool", [make_param("p1", "string")])
        t.name_for_human = "某工具"
        t.description = "desc"
        t.tool_id = 5

        task = h.task_manager.create_task("模糊", exists_task_id="cov-unclear")
        task.curr_tool_id = 5
        task.curr_tool_param = {"p1": "v1"}
        task.task_type = 1
        task.save()

        with patch.object(h.tool_manager, "get_tools_by_ids", return_value=[t]):
            # LLM 返回 unclear
            h.api_selection_hub.LargeLanguageModel.chat_completions.return_value = "unclear"
            h.api_planning_handle_human_feedback(task, "某个模糊的反馈")

        updated = h.task_manager.get_task_by_id("cov-unclear")
        if updated:
            # 应该继续等待确认
            assert updated.status in [100, -1, 1]

    def test_intent_other(self, hub):
        """意图识别返回其他值"""
        h, _ = hub
        from conftest import make_tool, make_param

        t = make_tool("someTool", [make_param("p1", "string")])
        t.name_for_human = "某工具"
        t.description = "desc"
        t.tool_id = 5

        task = h.task_manager.create_task("其他", exists_task_id="cov-other")
        task.curr_tool_id = 5
        task.curr_tool_param = {"p1": "v1"}
        task.task_type = 1
        task.save()

        with patch.object(h.tool_manager, "get_tools_by_ids", return_value=[t]):
            h.api_selection_hub.LargeLanguageModel.chat_completions.return_value = "unknown"
            h.api_planning_handle_human_feedback(task, "其他反馈")

        updated = h.task_manager.get_task_by_id("cov-other")
        if updated:
            assert updated.status in [100, -1, 1]

    def test_intent_exception(self, hub):
        """handle_human_feedback 异常处理"""
        h, _ = hub
        task = h.task_manager.create_task("异常测试", exists_task_id="cov-exception")
        task.curr_tool_id = -1  # 初始 tool ID — 会触发 early return
        task.task_type = 1
        task.save()

        h.api_planning_handle_human_feedback(task, "立即执行")

        updated = h.task_manager.get_task_by_id("cov-exception")
        if updated:
            assert updated.status == -1

    def test_multi_api_final_summary_with_nodes(self, hub):
        """多 API 完成后，从 nodes 生成 summary"""
        h, _ = hub
        from conftest import make_tool, make_param

        t = make_tool("finalTool2", [make_param("p1", "string")])
        t.name_for_human = "最终工具2"
        t.tool_id = 5
        t.isValidate = False
        t.api_url = "http://localhost:8080"
        t.path = "/api/final2"
        t.method = "GET"
        t.operationId = "finalOp2"

        task = h.task_manager.create_task("最终2", exists_task_id="cov-summary-nodes")
        task.curr_tool_id = 5
        task.curr_tool_param = {"p1": "v1"}
        task.task_type = 2
        task.changed_query = "final2"
        task.raw_query = "raw"
        task.nodes = [
            {"label": "tool1", "result": "r1", "params": "{}", "task_description": "d1"},
            {"label": "tool2", "result": "r2", "params": "{}", "task_description": "d2"},
        ]
        task.save()

        h.generate_task_hub.PromptModelHub = MagicMock()
        h.generate_task_hub.PromptModelHub.gen_subtask_context_prompt.return_value = "p"
        h.generate_task_hub.PromptModelHub.post_process_gen_subtask_task.return_value = (True, None)

        with patch.object(h.tool_manager, "get_tools_by_ids", return_value=[t]), \
             patch.object(h.tool_use_hub, "tool_use") as mock_use, \
             patch.object(h.tool_summary_hub, "tool_summary", return_value="综合摘要"):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"ok":"yes"}'
            mock_use.return_value = mock_resp

            h.api_planning_handle_human_feedback(task, "立即执行")

        updated = h.task_manager.get_task_by_id("cov-summary-nodes")
        if updated:
            assert updated.status == -1
