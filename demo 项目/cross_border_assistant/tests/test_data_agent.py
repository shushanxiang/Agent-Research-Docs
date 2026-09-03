# -*- coding: utf-8 -*-
"""graph/data_agent.py 测试：SQL/JSON 提取、schema 注入、节点完整流程、异常兜底"""
import inspect
import json
import pytest
import graph.data_agent as da
from db.duckdb_manager import SessionDB
from conftest import make_state


# ---------- extract_sql_from_llm（兼容旧接口） ----------

def test_extract_sql_from_markdown_block():
    resp = "```sql\nSELECT date, sales FROM t\n```"
    assert da.extract_sql_from_llm(resp) == "SELECT date, sales FROM t"


def test_extract_sql_plain():
    resp = "SELECT date, sales FROM t;"
    assert da.extract_sql_from_llm(resp) == "SELECT date, sales FROM t"


def test_extract_sql_no_select_returns_raw():
    resp = "some plain text"
    assert da.extract_sql_from_llm(resp) == "some plain text"


# ---------- extract_json_from_llm ----------

def test_extract_json_from_markdown_block():
    resp = '```json\n{"sql": "SELECT 1", "need_chart": false, "chart_type": "line"}\n```'
    parsed = da.extract_json_from_llm(resp)
    assert parsed["sql"] == "SELECT 1"
    assert parsed["need_chart"] is False


def test_extract_json_plain():
    resp = '{"sql": "SELECT 1", "need_chart": true, "chart_type": "bar"}'
    assert da.extract_json_from_llm(resp)["chart_type"] == "bar"


def test_extract_json_with_surrounding_text():
    resp = '好的，以下是结果：\n{"sql": "SELECT 1", "need_chart": false} 完成'
    parsed = da.extract_json_from_llm(resp)
    assert parsed["sql"] == "SELECT 1"


def test_extract_json_invalid_returns_none():
    assert da.extract_json_from_llm("不是JSON") is None
    assert da.extract_json_from_llm("LLM调用失败: xxx") is None


# ---------- schema 注入 ----------

def test_schema_context_contains_columns(sample_csv, tmp_path):
    db = SessionDB(str(tmp_path / "t.db"))
    table = db.upload_file("s1", sample_csv, "sales.csv")
    context = da._build_schema_context(db, [table])
    assert table in context
    assert "date" in context and "sales" in context and "orders" in context
    assert "示例数据" in context


def test_system_prompt_requires_json(sample_csv, tmp_path):
    db = SessionDB(str(tmp_path / "t.db"))
    table = db.upload_file("s1", sample_csv, "sales.csv")
    schema = da._build_schema_context(db, [table])
    prompt = da._build_system_prompt(schema)
    assert "need_chart" in prompt and "chart_type" in prompt and '"sql"' in prompt
    assert "answer_type" in prompt


# ---------- 回答式总结（列表型/汇总型） ----------

def test_summary_prompt_list_type(sample_csv, tmp_path):
    db = SessionDB(str(tmp_path / "t.db"))
    table = db.upload_file("s1", sample_csv, "sales.csv")
    df = db.execute_sql("s1", f"SELECT date, sales FROM {table}")
    prompt = da._build_summary_prompt("列出库存低于50的SKU及库存数", df, "list")
    assert "列出所有条目" in prompt
    assert "不要做趋势" in prompt  # 禁止额外分析
    assert "共4行" in prompt
    assert "SKU" in prompt or "库存" in prompt


def test_summary_prompt_summary_type(sample_csv, tmp_path):
    db = SessionDB(str(tmp_path / "t.db"))
    table = db.upload_file("s1", sample_csv, "sales.csv")
    df = db.execute_sql("s1", f"SELECT SUM(sales) AS total FROM {table}")
    prompt = da._build_summary_prompt("统计销售总额", df, "summary")
    assert "关键发现" in prompt
    assert "共1行" in prompt


def test_system_prompt_predict_guidance(sample_csv, tmp_path):
    """预测类查询：prompt 引导基于历史聚合推断"""
    db = SessionDB(str(tmp_path / "t.db"))
    table = db.upload_file("s1", sample_csv, "sales.csv")
    schema = da._build_schema_context(db, [table])
    prompt = da._build_system_prompt(schema, data_type="predict")
    assert "预测" in prompt
    assert "聚合" in prompt


def test_system_prompt_vague_guidance(sample_csv, tmp_path):
    """模糊查看：prompt 引导生成简单浏览 SQL"""
    db = SessionDB(str(tmp_path / "t.db"))
    table = db.upload_file("s1", sample_csv, "sales.csv")
    schema = da._build_schema_context(db, [table])
    prompt = da._build_system_prompt(schema, data_type="vague")
    assert "模糊" in prompt
    assert "LIMIT" in prompt


# ---------- data_agent_node ----------

def _fake_llm_json(table, summary="销售额整体呈上升趋势。", answer_type="summary"):
    """构造返回 JSON 决策 + 回答式总结的 mock LLM"""

    def fake(prompt, system_prompt=None):
        if "【总结】" in prompt:
            return summary
        return json.dumps(
            {
                "sql": f"SELECT date, sales FROM {table} ORDER BY date",
                "need_chart": True,
                "chart_type": "line",
                "answer_type": answer_type,
            }
        )

    return fake


def test_data_agent_node_no_tables(tmp_path):
    db = SessionDB(str(tmp_path / "t.db"))
    state = make_state([{"role": "user", "content": "查询数据"}])
    result = da.data_agent_node(state, db)
    assert "未上传任何数据" in result["error"]


def test_data_agent_node_vague_guides_user(sample_csv, tmp_path, monkeypatch):
    """模糊查看（问题9）：返回引导提示，不执行 SQL 也不调用 LLM"""
    db = SessionDB(str(tmp_path / "t.db"))
    db.upload_file("s1", sample_csv, "sales.csv")

    called = {"n": 0}
    monkeypatch.setattr(da, "call_llm", lambda prompt, system_prompt=None: called.__setitem__("n", called["n"] + 1) or "{}")
    state = make_state([{"role": "user", "content": "帮我看看数据"}], data_type="vague", uploaded_files=["file_x"])
    result = da.data_agent_node(state, db)
    out = result["execution_result"]
    assert out["type"] == "data"
    assert out["answer_type"] == "vague"
    assert "请明确具体操作" in out["summary"]
    assert "展示7月每日总销售额趋势图" in out["summary"]
    assert called["n"] == 0  # 未调用 LLM


def test_data_agent_node_full_flow(sample_csv, tmp_path, monkeypatch):
    db = SessionDB(str(tmp_path / "t.db"))
    table = db.upload_file("s1", sample_csv, "sales.csv")

    monkeypatch.setattr(da, "call_llm", _fake_llm_json(table))
    state = make_state(
        [{"role": "user", "content": "查询每日销售额趋势"}],
        uploaded_files=[table],
    )
    result = da.data_agent_node(state, db)
    out = result["execution_result"]
    assert out["type"] == "data"
    assert out["sql"].upper().startswith("SELECT")
    assert len(out["dataframe"]) == 4
    assert out["total_rows"] == 4
    # LLM 决策 need_chart=true → 生成折线图
    assert out["chart"] and out["chart"].startswith("data:image/png;base64,")
    assert out["chart_type"] == "line"
    assert out["answer_type"] == "summary"
    assert out["summary"]


def test_data_agent_node_sql_fix_retry(sample_csv, tmp_path, monkeypatch):
    """第一次 SQL 执行失败 → 携带 schema 修正重试，最终成功"""
    db = SessionDB(str(tmp_path / "t.db"))
    table = db.upload_file("s1", sample_csv, "sales.csv")

    def fake_llm(prompt, system_prompt=None):
        if "【总结】" in prompt:
            return "总结"
        if "SQL执行失败" in prompt:
            return json.dumps(
                {"sql": f"SELECT date, sales FROM {table} ORDER BY date", "need_chart": False, "chart_type": "line", "answer_type": "summary"}
            )
        return json.dumps({"sql": "SELECT * FROM nonexistent_table", "need_chart": False, "chart_type": "line", "answer_type": "summary"})

    monkeypatch.setattr(da, "call_llm", fake_llm)
    state = make_state([{"role": "user", "content": "查询数据"}], uploaded_files=[table])
    result = da.data_agent_node(state, db)
    assert result["execution_result"]["type"] == "data"


def test_data_agent_node_sql_fix_fails_gracefully(sample_csv, tmp_path, monkeypatch):
    """修正后 SQL 仍非法时返回友好 error，不抛异常冒泡"""
    db = SessionDB(str(tmp_path / "t.db"))
    db.upload_file("s1", sample_csv, "sales.csv")

    def fake_llm(prompt, system_prompt=None):
        return json.dumps({"sql": "DELETE FROM file_x", "need_chart": False, "chart_type": "line"})

    monkeypatch.setattr(da, "call_llm", fake_llm)
    state = make_state([{"role": "user", "content": "查询数据"}], uploaded_files=["file_x"])
    result = da.data_agent_node(state, db)
    assert "error" in result
    assert "SQL执行失败" in result["error"]
    assert result["execution_result"] is None


def test_data_agent_node_llm_failure_clear_error(sample_csv, tmp_path, monkeypatch):
    """LLM 不可用（额度耗尽等）时直接返回明确错误"""
    db = SessionDB(str(tmp_path / "t.db"))
    db.upload_file("s1", sample_csv, "sales.csv")

    monkeypatch.setattr(
        da, "call_llm", lambda prompt, system_prompt=None: "LLM调用失败: API Error: Free quota exhausted"
    )
    state = make_state([{"role": "user", "content": "查询数据"}], uploaded_files=["file_x"])
    result = da.data_agent_node(state, db)
    assert "error" in result
    assert "生成SQL失败" in result["error"]
    assert result["execution_result"] is None


def test_data_agent_node_no_chart_when_llm_says_false(sample_csv, tmp_path, monkeypatch):
    """LLM 决策 need_chart=false 时即使查询词含'趋势'也不画图"""
    db = SessionDB(str(tmp_path / "t.db"))
    table = db.upload_file("s1", sample_csv, "sales.csv")

    def fake_llm(prompt, system_prompt=None):
        if "【总结】" in prompt:
            return "总结"
        return json.dumps(
            {"sql": f"SELECT date, sales FROM {table} ORDER BY date", "need_chart": False, "chart_type": "line", "answer_type": "summary"}
        )

    monkeypatch.setattr(da, "call_llm", fake_llm)
    state = make_state([{"role": "user", "content": "查询销售额趋势"}], uploaded_files=[table])
    result = da.data_agent_node(state, db)
    out = result["execution_result"]
    assert out["chart"] is None
    assert out["chart_type"] is None


def test_data_agent_node_requires_db_manager():
    """data_agent_node 签名为 (state, db_manager)，直接缺参调用应抛 TypeError"""
    state = make_state([{"role": "user", "content": "查询"}])
    with pytest.raises(TypeError, match="db_manager"):
        da.data_agent_node(state)


def test_data_agent_node_signature_has_two_params():
    sig = inspect.signature(da.data_agent_node)
    assert list(sig.parameters) == ["state", "db_manager"]
