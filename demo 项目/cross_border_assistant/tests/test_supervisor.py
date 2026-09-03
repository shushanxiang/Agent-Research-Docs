# -*- coding: utf-8 -*-
"""graph/supervisor.py 测试：结构化 JSON 意图识别（mock LLM）"""
import json
import graph.supervisor as sup
from conftest import make_state


def _run(query, fake_json, monkeypatch, with_image=False):
    monkeypatch.setattr(sup, "call_llm", lambda prompt, system_prompt=None, **kwargs: fake_json)
    state = make_state([{"role": "user", "content": query}])
    if with_image:
        state["current_image_url"] = "C:/tmp/img.png"
    return sup.supervisor_node(state)


def test_intent_data_trend(monkeypatch):
    r = _run("展示7月每日总销售额趋势图", '{"intent":"data","data_type":"trend","need_image":false}', monkeypatch)
    assert r["intent"] == "data"
    assert r["data_type"] == "trend"
    assert r["need_image"] is False


def test_intent_data_list(monkeypatch):
    r = _run("列出库存低于50的SKU", '{"intent":"data","data_type":"list","need_image":false}', monkeypatch)
    assert r["data_type"] == "list"


def test_intent_data_predict(monkeypatch):
    r = _run("预测下个月哪个品类销量最高", '{"intent":"data","data_type":"predict","need_image":false}', monkeypatch)
    assert r["data_type"] == "predict"


def test_intent_data_vague(monkeypatch):
    r = _run("帮我看看数据", '{"intent":"data","data_type":"vague","need_image":false}', monkeypatch)
    assert r["data_type"] == "vague"


def test_intent_listing(monkeypatch):
    r = _run("生成三种风格的Listing", '{"intent":"listing","data_type":null,"need_image":false}', monkeypatch)
    assert r["intent"] == "listing"
    assert r["data_type"] is None


def test_intent_image(monkeypatch):
    r = _run("生成产品场景图", '{"intent":"image","data_type":null,"need_image":false}', monkeypatch)
    assert r["intent"] == "image"


def test_intent_evaluate(monkeypatch):
    r = _run("评估这条Listing的质量", '{"intent":"evaluate","data_type":null,"need_image":false}', monkeypatch)
    assert r["intent"] == "evaluate"


def test_need_image_true(monkeypatch):
    """用户提到上传主图且用于任务 → need_image=true"""
    r = _run("基于主图生成4张场景图", '{"intent":"image","data_type":null,"need_image":true}', monkeypatch)
    assert r["need_image"] is True


def test_fallback_data_on_garbage(monkeypatch):
    """LLM 输出无法解析时回退 data"""
    r = _run("随便聊聊", "不是JSON内容", monkeypatch)
    assert r["intent"] == "data"
    assert r["data_type"] is None


def test_rule_fallback_corrects_vague(monkeypatch):
    """规则兜底：LLM 降级误判为 vague 时，按 query 关键词修正 data_type"""
    cases = [
        ("展示7月每日总销售额趋势图", "trend"),
        ("列出库存低于50的SKU及库存数", "list"),
        ("按品类统计7月份的总销量和平均广告费", "stat"),
        ("哪个SKU销售额最高？帮我查一下", "stat"),
        ("分析一下食品类在7月下半月的销售趋势", "trend"),
        ("预测下个月哪个品类销量最高", "predict"),
    ]
    for query, expected in cases:
        r = _run(query, '{"intent":"data","data_type":"vague","need_image":false}', monkeypatch)
        assert r["data_type"] == expected, f"{query} → {r['data_type']}, 期望 {expected}"


def test_rule_fallback_keeps_true_vague(monkeypatch):
    """真正的模糊查询（帮我看看数据）不应被规则误改"""
    r = _run("帮我看看数据", '{"intent":"data","data_type":"vague","need_image":false}', monkeypatch)
    assert r["data_type"] == "vague"


def test_guess_data_type_direct():
    assert sup._guess_data_type("预测下个月哪个品类销量最高") == "predict"
    assert sup._guess_data_type("展示7月每日总销售额趋势图") == "trend"
    assert sup._guess_data_type("列出库存低于50的SKU") == "list"
    assert sup._guess_data_type("按品类统计总销量") == "stat"
    assert sup._guess_data_type("帮我看看数据") is None


def test_invalid_intent_falls_back_data(monkeypatch):
    r = _run("你好", '{"intent":"chat","data_type":"x","need_image":false}', monkeypatch)
    assert r["intent"] == "data"
    assert r["data_type"] is None


def test_prompt_contains_examples_and_query(monkeypatch):
    captured = {}

    def fake_llm(prompt, system_prompt=None, **kwargs):
        captured["prompt"] = prompt
        return '{"intent":"data","data_type":"list","need_image":false}'

    monkeypatch.setattr(sup, "call_llm", fake_llm)
    state = make_state([{"role": "user", "content": "列出库存"}])
    sup.supervisor_node(state)
    assert "列出库存" in captured["prompt"]
    assert "参考示例" in captured["prompt"]
    assert "data_type" in captured["prompt"]
