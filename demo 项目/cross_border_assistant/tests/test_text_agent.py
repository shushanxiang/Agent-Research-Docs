# -*- coding: utf-8 -*-
"""graph/text_agent.py 测试：Listing 生成（mock LLM / VL / 敏感词）"""
import graph.text_agent as ta
from conftest import make_state

FAKE_LISTING = """Title: Eco Friendly Water Bottle
Bullet Points:
- Durable stainless steel
- Leak proof design
- Portable size
- BPA free material
- Easy to clean
Description: A great eco bottle for daily use.
Keywords: eco, bottle, durable, portable"""


def test_text_agent_generates_three_styles(monkeypatch):
    monkeypatch.setattr(ta, "call_llm", lambda prompt, system_prompt=None: FAKE_LISTING)
    state = make_state([{"role": "user", "content": "生成3种风格Listing"}], current_image_url=None)
    result = ta.text_agent_node(state)
    out = result["execution_result"]
    assert out["type"] == "listing"
    assert len(out["listings"]) == 3
    for lst in out["listings"]:
        assert lst["style"] in ("专业严谨型", "促销冲动型", "场景体验型")
        assert "raw" in lst and "filtered_html" in lst
        assert "hits" in lst and "has_issue" in lst


def test_text_agent_with_image_uses_vl(monkeypatch):
    """存在 current_image_url 时调用 VL 识别，并把描述注入 prompt"""
    captured = {}

    def fake_vl(url, prompt):
        captured["url"] = url
        return "蓝色塑料环保水瓶，轻便耐用"

    def fake_llm(prompt, system_prompt=None):
        captured["prompt"] = prompt
        return FAKE_LISTING

    monkeypatch.setattr(ta, "call_vl", fake_vl)
    monkeypatch.setattr(ta, "call_llm", fake_llm)
    state = make_state(
        [{"role": "user", "content": "生成Listing"}],
        current_image_url="http://example.com/p.png",
    )
    result = ta.text_agent_node(state)
    assert result["execution_result"]["image_desc"] == "蓝色塑料环保水瓶，轻便耐用"
    assert captured["url"] == "http://example.com/p.png"
    assert "蓝色塑料环保水瓶" in captured["prompt"]


def test_text_agent_sensitive_word_flagged(monkeypatch):
    """内容含敏感词时 has_issue=True 且 hits 非空"""
    listing_with_issue = "Title: Best product ever\n" + FAKE_LISTING.split("\n", 1)[1]

    monkeypatch.setattr(ta, "call_llm", lambda prompt, system_prompt=None: listing_with_issue)
    state = make_state([{"role": "user", "content": "生成Listing"}], current_image_url=None)
    result = ta.text_agent_node(state)
    first = result["execution_result"]["listings"][0]
    assert first["has_issue"] is True
    assert "best" in first["hits"]


def test_text_agent_llm_failure_no_false_positive(monkeypatch):
    """回归：LLM 不可用（额度耗尽等）时，不把错误文本当 Listing 内容，
    也不对其做敏感词过滤（避免错误信息里的 'only' 等词被误报）"""
    monkeypatch.setattr(
        ta,
        "call_llm",
        lambda prompt, system_prompt=None: "LLM调用失败: API Error: Free quota exhausted",
    )
    state = make_state([{"role": "user", "content": "生成Listing"}], current_image_url=None)
    result = ta.text_agent_node(state)
    for lst in result["execution_result"]["listings"]:
        assert lst["llm_error"].startswith("LLM调用失败")
        assert lst["has_issue"] is False  # 错误信息不触发敏感词误报
        assert lst["hits"] == []


def test_text_agent_vl_failure_degrades_gracefully(monkeypatch):
    """回归：VL 图片识别失败（额度耗尽抛异常）时降级为纯文本生成，不崩溃"""
    def boom(url, prompt):
        raise Exception("VL Error: Free quota exhausted")

    monkeypatch.setattr(ta, "call_vl", boom)
    monkeypatch.setattr(ta, "call_llm", lambda prompt, system_prompt=None: FAKE_LISTING)
    state = make_state(
        [{"role": "user", "content": "生成Listing"}],
        current_image_url="http://example.com/p.png",
    )
    result = ta.text_agent_node(state)
    out = result["execution_result"]
    assert out["type"] == "listing"
    assert len(out["listings"]) == 3  # 正常生成三风格
    assert "图片识别服务暂不可用" in out["image_desc"]
