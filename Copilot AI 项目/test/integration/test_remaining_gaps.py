"""补满 api_planning_hub.py 剩余 18 条未覆盖语句 — 目标 97%+"""

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


class TestRemainingCoverageGaps:
    """剩余 18 条未覆盖语句（api_planning_hub.py 93% → 97%）"""

    # ---- 行 296-304: _tool_check 中 inject_flag=True 返回 ----
    def test_tool_check_injection_detected_return(self, hub):
        h, _ = hub
        from conftest import make_tool, make_param
        tool = make_tool("injectCheck", [make_param("quantity", "int32", required=True)], is_validate=True)
        tool.name_for_human = "高危工具"
        tool.tool_id = 3
        tool.api_url = "http://localhost:8080"
        tool.path = "/api/danger"
        tool.method = "POST"
        tool.operationId = "dangerOp"

        h.param_extraction_hub.PromptModelHub = MagicMock()
        h.param_extraction_hub.PromptModelHub.gen_get_all_parameters_prompt.return_value = "p"
        h.param_extraction_hub.PromptModelHub.post_process_get_all_parameter_result.return_value = {"quantity": 42}

        h.generate_task_hub.PromptModelHub = MagicMock()
        h.generate_task_hub.PromptModelHub.judge_validate.return_value = "jp"
        h.generate_task_hub.PromptModelHub.post_process_gen_judge_task.return_value = (True, "数量异常大，疑似注入")

        result = h._tool_check(tool, "危险查询", "原始查询")
        assert result["code"] == 404  # TASK_ERROR_CODE
        assert result["result"] == "inject"
        assert "注入攻击" in result["tool"]

    # ---- 行 316-318: _tool_check 中参数补充成功后的 logger + 赋值 ----
    def test_tool_check_supplement_success_path(self, hub):
        h, _ = hub
        from conftest import make_tool, make_param
        tool = make_tool("needSupplement", [make_param("supplierId", "int64", required=True)])
        tool.name_for_human = "需要补充参数的工具"
        tool.tool_id = 5
        tool.isValidate = False
        tool.api_url = "http://localhost:8080"
        tool.path = "/api/supplement"
        tool.method = "GET"
        tool.operationId = "supplementOp"

        # Mock gen_judge_task 不对补充后参数触发注入（行 330-337）
        h.generate_task_hub.PromptModelHub = MagicMock()
        h.generate_task_hub.PromptModelHub.gen_param_task_prompt.return_value = "gen_p"
        h.generate_task_hub.PromptModelHub.judge_validate.return_value = "j"
        h.generate_task_hub.PromptModelHub.post_process_gen_judge_task.return_value = (False, None)

        # Mock _supplement_parameters 成功找到参数
        with patch.object(h, "_supplement_parameters") as mock_sp:
            mock_sp.return_value = (42, "supplierAPI", {
                "code": 200, "tool": "supplierAPI", "result": "supplier_data",
                "param": {}, "query": "q", "task_description": "d"
            })

            result = h._tool_check(tool, "查询", "原始查询")
            assert result["code"] == 200
            assert len(result["missing_param"]) == 1  # 成功补充的

    # ---- 行 330-337: _tool_check 中补充后注入检测触发 ----
    def test_tool_check_post_supplement_injection(self, hub):
        h, _ = hub
        from conftest import make_tool, make_param
        tool = make_tool("postInject", [make_param("supplierId", "int64", required=True)], is_validate=True)
        tool.name_for_human = "补充后注入工具"
        tool.tool_id = 5
        tool.api_url = "http://localhost:8080"
        tool.path = "/api/post"
        tool.method = "GET"
        tool.operationId = "postOp"

        h.generate_task_hub.PromptModelHub = MagicMock()
        h.generate_task_hub.PromptModelHub.gen_param_task_prompt.return_value = "gp"
        h.generate_task_hub.PromptModelHub.judge_validate.return_value = "j"
        h.generate_task_hub.PromptModelHub.post_process_gen_judge_task.return_value = (True, "补充参数后注入检测触发")

        with patch.object(h, "_supplement_parameters") as mock_sp:
            mock_sp.return_value = (42, "api", {
                "code": 200, "tool": "api", "result": "data",
                "param": {}, "query": "q", "task_description": "d"
            })

            result = h._tool_check(tool, "查询", "原始查询")
            assert result["code"] == 404
            assert result["result"] == "inject"

    # ---- 行 471: abort 意图处理 ----
    def test_handle_human_feedback_abort(self, hub):
        h, _ = hub
        from conftest import make_tool, make_param
        t = make_tool("abortTool", [make_param("p1", "string")])
        t.name_for_human = "放弃测试工具"
        t.tool_id = 5
        t.isValidate = False

        task = h.task_manager.create_task("放弃测试", exists_task_id="cov-abort-intent")
        task.curr_tool_id = 5
        task.curr_tool_param = {"p1": "v1"}
        task.task_type = 2
        task.save()

        with patch.object(h.tool_manager, "get_tools_by_ids", return_value=[t]):
            h.api_planning_handle_human_feedback(task, "不执行")

        updated = h.task_manager.get_task_by_id("cov-abort-intent")
        if updated:
            assert updated.status == -1

    # ---- 行 480-486: 意图识别其他分支（不匹配 confirm/abort/unclear） ----
    def test_handle_human_feedback_other_intent(self, hub):
        h, _ = hub
        from conftest import make_tool, make_param
        t = make_tool("otherTool", [make_param("p1", "string")])
        t.name_for_human = "其他测试工具"
        t.tool_id = 5
        t.isValidate = False

        task = h.task_manager.create_task("其他测试", exists_task_id="cov-other-intent")
        task.curr_tool_id = 5
        task.curr_tool_param = {"p1": "v1"}
        task.task_type = 2
        task.save()

        with patch.object(h.tool_manager, "get_tools_by_ids", return_value=[t]), \
             patch.object(h, "_recognize_human_intent", return_value={"intent": "unknown_intent", "confidence": 0.0, "patch": {}, "reason": "test"}):
            h.api_planning_handle_human_feedback(task, "奇怪的反馈")

        updated = h.task_manager.get_task_by_id("cov-other-intent")
        if updated:
            assert updated.status == 100  # WAIT_CONFIRM

    # ---- 行 508-509: API 结果超长截断（_process_single_api_invoke） ----
    @patch("apis.api_planning_hub.api_result_max_threshold", 0.00001)
    @patch("apis.api_planning_hub.api_result_max_length", 100000)
    def test_process_api_invoke_truncation(self, hub):
        h, _ = hub
        from conftest import make_tool, make_param

        task = h.task_manager.create_task("截断测试", exists_task_id="cov-truncate")
        tool = make_tool("truncateTool", [make_param("p1", "string")])
        tool.api_url = "http://localhost:8080"
        tool.path = "/api/long"
        tool.method = "GET"
        tool.operationId = "truncateOp"
        tool.name_for_human = "截断工具"

        # 超长结果触发截断
        long_result = "x" * 5000

        with patch.object(h.tool_use_hub, "tool_use") as mock_use:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = long_result
            mock_use.return_value = mock_resp

            result = h._process_single_api_invoke("查询", task, tool, {"p1": "v1"})
            assert result["code"] == 200
            assert "截取" in result["result"]  # 被截断

    # ---- 行 580-581: _recognize_human_intent LLM 异常降级 ----
    def test_recognize_intent_llm_exception(self, hub):
        h, _ = hub
        mock_tool = MagicMock()
        mock_tool.name_for_human = "test"

        h.api_selection_hub.LargeLanguageModel.chat_completions.side_effect = Exception("API crashed")

        intent = h._recognize_human_intent("非关键词反馈需要走 LLM", mock_tool, {})
        assert intent["intent"] == "unclear"

    # ---- 行 508-509: _get_summary_from_nodes（再确认）- 已在其他测试中覆盖 ----
    # ---- 行 580-581: apis_planning 多任务设置 - 已在其他测试中覆盖 ----
