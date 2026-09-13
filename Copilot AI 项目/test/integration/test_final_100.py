"""覆盖最后 5 条未覆盖语句: 98% → 100%"""

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


class TestFinalGaps:
    """最后 5 条语句: 行 333-339, 行 484-486"""

    # ---- 行 333-339: _tool_check 补充参数后 gen_judge_task 触发注入 ----
    def test_tool_check_supplement_then_inject(self, hub):
        h, _ = hub
        from conftest import make_tool, make_param
        tool = make_tool("finalInject", [make_param("supplierId", "int64", required=True)], is_validate=True)
        tool.name_for_human = "最终注入测试"
        tool.tool_id = 5
        tool.api_url = "http://localhost:8080"
        tool.path = "/api/finalinject"
        tool.method = "GET"
        tool.operationId = "finalInjectOp"

        # 参数缺失 → 走参数补充流程 → 补全后 gen_judge_task → inject_flag=True
        h.param_extraction_hub.PromptModelHub = MagicMock()
        h.param_extraction_hub.PromptModelHub.gen_get_all_parameters_prompt.return_value = "p"
        h.param_extraction_hub.PromptModelHub.post_process_get_all_parameter_result.return_value = {}

        h.generate_task_hub.PromptModelHub = MagicMock()
        h.generate_task_hub.PromptModelHub.gen_param_task_prompt.return_value = "gp"
        h.generate_task_hub.PromptModelHub.judge_validate.return_value = "j"
        h.generate_task_hub.PromptModelHub.post_process_gen_judge_task.return_value = (True, "补充后检测到注入")

        with patch.object(h, "_supplement_parameters") as mock_sp:
            mock_sp.return_value = (99, "supplierAPI", {
                "code": 200, "tool": "supplierAPI", "result": "data",
                "param": {}, "query": "q", "task_description": "d"
            })

            result = h._tool_check(tool, "查询", "原始查询")
            assert result["code"] == 404  # TASK_ERROR_CODE
            assert result["result"] == "inject"
            assert "提示注入攻击" in result["tool"]

    # ---- 行 484-486: api_planning_handle_human_feedback 顶层 except ----
    def test_handle_human_feedback_top_level_exception(self, hub):
        h, _ = hub
        task = h.task_manager.create_task("顶层异常测试", exists_task_id="cov-top-exc-unique")
        task.curr_tool_id = 5
        task.curr_tool_param = {"p1": "v1"}
        task.task_type = 1
        task.save()

        # 让 _recognize_human_intent 返回 confirm，从而进入执行分支
        # 方案 11 后返回 dict 而非字符串
        with patch.object(h, "_recognize_human_intent", return_value={"intent": "confirm", "confidence": 1.0, "patch": {}, "reason": "test"}), \
             patch.object(h.tool_manager, "get_tools_by_ids", side_effect=Exception("MongoDB崩溃")):
            h.api_planning_handle_human_feedback(task, "立即执行")

        updated = h.task_manager.get_task_by_id("cov-top-exc-unique")
        if updated:
            assert updated.status == -1  # FINISH
