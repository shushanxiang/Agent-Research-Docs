# -*- coding: utf-8 -*-
"""graph/workflow.py 测试：路由函数、图构建、端到端运行情况"""
import json
import pytest
from graph.workflow import build_workflow, route_after_supervisor
from conftest import make_state


# ---------- 路由函数 ----------

def test_route_all_intents():
    assert route_after_supervisor({"intent": "data"}) == "data_agent"
    assert route_after_supervisor({"intent": "listing"}) == "text_agent"
    assert route_after_supervisor({"intent": "image"}) == "image_agent"
    assert route_after_supervisor({"intent": "evaluate"}) == "evaluator"


def test_route_unknown_defaults_to_data():
    assert route_after_supervisor({}) == "data_agent"
    assert route_after_supervisor({"intent": "haha"}) == "data_agent"


# ---------- 图构建 ----------

def test_build_workflow_succeeds(tmp_path):
    from db.duckdb_manager import SessionDB

    db = SessionDB(str(tmp_path / "t.db"))
    wf = build_workflow(db_manager=db)
    assert wf is not None
    # 图中应包含 5 个节点
    assert set(wf.get_graph().nodes) >= {
        "supervisor",
        "data_agent",
        "text_agent",
        "image_agent",
        "evaluator",
    }


# ---------- 端到端运行情况（修复后） ----------

def _data_llm_fake(table):
    """模拟 data_agent 的 LLM：返回 JSON 决策 + 回答式总结"""

    def fake(prompt, system_prompt=None):
        if "【总结】" in prompt:
            return "总结：销售额共570。"
        return json.dumps(
            {"sql": f"SELECT date, sales FROM {table}", "need_chart": True, "chart_type": "line", "answer_type": "summary"}
        )

    return fake


def test_workflow_invoke_data_intent_end_to_end(sample_csv, tmp_path, monkeypatch):
    """修复后：data 意图完整跑通——真实 DuckDB + mock LLM，
    验证 supervisor→路由→data_agent→图表/结论 全链路。"""
    import graph.supervisor as sup
    import graph.data_agent as da
    from db.duckdb_manager import SessionDB

    db = SessionDB(str(tmp_path / "t.db"))
    table = db.upload_file("s1", sample_csv, "sales.csv")

    monkeypatch.setattr(sup, "call_llm", lambda prompt, system_prompt=None, **kwargs: '{"intent":"data","data_type":"trend","need_image":false}')
    monkeypatch.setattr(da, "call_llm", _data_llm_fake(table))

    wf = build_workflow(db_manager=db)
    state = make_state(
        [{"role": "user", "content": "查询每日销售额趋势"}],
        uploaded_files=[table],
    )
    result = wf.invoke(state)
    assert result["intent"] == "data"
    out = result["execution_result"]
    assert out["type"] == "data"
    assert out["sql"].upper().startswith("SELECT")
    assert len(out["dataframe"]) == 4
    assert out["chart"] and out["chart"].startswith("data:image/png;base64,")  # 触发绘图
    assert out["summary"]


def test_workflow_invoke_listing_intent_end_to_end(tmp_path, monkeypatch):
    """修复后：listing 意图完整跑通——supervisor 路由到 text_agent，
    生成 3 种风格 Listing（mock LLM）。"""
    import graph.supervisor as sup
    import graph.text_agent as ta
    from db.duckdb_manager import SessionDB

    fake_listing = (
        "Title: Eco Friendly Water Bottle\n"
        "Bullet Points:\n- Durable\n- Leak proof\n- Portable\n- BPA free\n- Easy to clean\n"
        "Description: A great eco bottle.\nKeywords: eco, bottle, durable"
    )

    db = SessionDB(str(tmp_path / "t.db"))  # 避免 build_workflow 使用默认路径
    monkeypatch.setattr(sup, "call_llm", lambda prompt, system_prompt=None, **kwargs: '{"intent":"listing","data_type":null,"need_image":false}')
    monkeypatch.setattr(ta, "call_llm", lambda prompt, system_prompt=None: fake_listing)

    wf = build_workflow(db_manager=db)
    state = make_state([{"role": "user", "content": "生成3种风格Listing"}])
    result = wf.invoke(state)
    assert result["intent"] == "listing"
    out = result["execution_result"]
    assert out["type"] == "listing"
    assert len(out["listings"]) == 3


def test_workflow_invoke_evaluate_intent_end_to_end(tmp_path, monkeypatch):
    """修复后：evaluate 意图完整跑通（mock LLM 建议生成）"""
    import graph.supervisor as sup
    import graph.evaluator as ev
    from db.duckdb_manager import SessionDB

    db = SessionDB(str(tmp_path / "t.db"))
    monkeypatch.setattr(sup, "call_llm", lambda prompt, system_prompt=None, **kwargs: '{"intent":"evaluate","data_type":null,"need_image":false}')
    monkeypatch.setattr(ev, "call_llm", lambda prompt, system_prompt=None: "建议1\n建议2\n建议3")

    wf = build_workflow(db_manager=db)
    state = make_state(
        [{"role": "user", "content": "评估Listing"}],
        target_listing="Title: Eco Friendly Bottle\nKeywords: eco, durable, natural",
        current_image_url="http://example.com/p.png",
    )
    result = wf.invoke(state)
    assert result["intent"] == "evaluate"
    assert result["execution_result"]["type"] == "evaluate"
    assert 0 <= result["execution_result"]["score"] <= 100


def test_workflow_messages_as_base_message_objects(sample_csv, tmp_path, monkeypatch):
    """修复后：langgraph 1.x 将 messages 归约为 BaseMessage 对象，
    各节点通过 get_last_content 兼容访问，不再抛 TypeError。"""
    import graph.supervisor as sup
    import graph.data_agent as da
    from db.duckdb_manager import SessionDB

    db = SessionDB(str(tmp_path / "t.db"))
    table = db.upload_file("s1", sample_csv, "sales.csv")

    monkeypatch.setattr(sup, "call_llm", lambda prompt, system_prompt=None, **kwargs: '{"intent":"data","data_type":"trend","need_image":false}')
    monkeypatch.setattr(da, "call_llm", _data_llm_fake(table))

    wf = build_workflow(db_manager=db)
    from langchain_core.messages import HumanMessage

    state = make_state([HumanMessage(content="查询销售额")], uploaded_files=[table])
    result = wf.invoke(state)
    assert result["execution_result"]["type"] == "data"
