# -*- coding: utf-8 -*-
"""graph/evaluator.py 测试：Listing 评分规则与建议生成（mock LLM）"""
import pytest
import graph.evaluator as ev
from conftest import make_state

GOOD_LISTING = """Title: Eco Friendly Water Bottle with Filter
Bullet Points:
- Durable stainless steel construction for long lasting use
- Leak proof lid keeps your bag dry on every journey
- Portable size fits most cup holders in car and office
- BPA free materials safe for you and your family
- Easy to clean dishwasher safe design saves your time
Description: This premium eco bottle is designed for active lifestyle. Made from natural materials with excellent heat retention, it keeps drinks cold for 24 hours and hot for 12. Perfect for office, gym, outdoor. Great gift choice for family and friends who care about the planet.
Keywords: eco bottle, natural, durable, portable, lightweight, stainless"""

WEAK_LISTING = """Title: bottle
Bullet Points:
- good
Description: short
Keywords: bottle"""


def _run(listing, monkeypatch, with_image=True):
    monkeypatch.setattr(ev, "call_llm", lambda prompt, system_prompt=None: "建议1\n建议2\n建议3")
    state = make_state(
        [{"role": "user", "content": "评估Listing"}],
        target_listing=listing,
        current_image_url="http://example.com/p.png" if with_image else None,
    )
    return ev.evaluator_node(state)


def test_evaluator_good_listing_high_score(monkeypatch):
    result = _run(GOOD_LISTING, monkeypatch)
    out = result["execution_result"]
    assert out["type"] == "evaluate"
    assert out["score"] >= 80  # 优秀 Listing 应拿到高分
    assert set(out["detail"].keys()) == {
        "title",
        "bullet_points",
        "description",
        "keywords",
        "image_quality",
    }
    assert len(out["suggestions"]) == 3


def test_evaluator_weak_listing_low_score(monkeypatch):
    result = _run(WEAK_LISTING, monkeypatch)
    out = result["execution_result"]
    assert out["score"] <= 40  # 极弱 Listing 分数应很低
    assert 0 <= out["score"] <= 100


def test_evaluator_default_listing_used_when_missing(monkeypatch):
    """state 未提供 target_listing 与 current_image_url 时使用内置示例，不应崩溃"""
    monkeypatch.setattr(ev, "call_llm", lambda prompt, system_prompt=None: "建议")
    state = make_state([{"role": "user", "content": "评估"}])  # 不含 current_image_url 键
    result = ev.evaluator_node(state)
    assert result["execution_result"]["type"] == "evaluate"


def test_evaluator_handles_none_image_url(monkeypatch):
    """修复后：current_image_url=None 不再崩溃，image_quality 按无图给 10 分"""
    monkeypatch.setattr(ev, "call_llm", lambda prompt, system_prompt=None: "建议")
    state = make_state(
        [{"role": "user", "content": "评估"}],
        target_listing=GOOD_LISTING,
        current_image_url=None,
    )
    result = ev.evaluator_node(state)
    out = result["execution_result"]
    assert out["type"] == "evaluate"
    assert out["detail"]["image_quality"] == 10  # 无图 → 10 分


def test_evaluator_llm_failure_default_advice(monkeypatch):
    """回归：LLM 不可用时（额度耗尽等），建议给默认提示，不展示错误文本"""
    monkeypatch.setattr(
        ev,
        "call_llm",
        lambda prompt, system_prompt=None: "LLM调用失败: API Error: Free quota exhausted",
    )
    state = make_state(
        [{"role": "user", "content": "评估"}],
        target_listing=GOOD_LISTING,
        current_image_url=None,
    )
    result = ev.evaluator_node(state)
    out = result["execution_result"]
    assert out["suggestions"] == ["LLM 服务暂不可用，请检查 API 额度或稍后重试。"]
    assert out["score"] >= 80  # 规则评分不受 LLM 影响


def test_evaluator_extracts_listing_from_single_line_query(monkeypatch):
    """参考问题7：评估内容在同一行消息中（标题/五点/描述/关键词），
    应从消息文本解析评估对象，而非默认示例"""
    monkeypatch.setattr(ev, "call_llm", lambda prompt, system_prompt=None: "建议1\n建议2\n建议3")
    query = (
        "评估这条Listing的质量：标题：Eco-friendly Water Bottle，"
        "五点：1. Made from recycled materials 2. Leak-proof design 3. BPA-free 4. Perfect for outdoor 5. Lifetime guarantee，"
        "描述：This water bottle is the best choice for eco-conscious consumers who care about the planet and want to reduce plastic waste every single day，"
        "关键词：water bottle, eco, reusable"
    )
    state = make_state([{"role": "user", "content": query}], current_image_url="http://example.com/p.png")
    result = ev.evaluator_node(state)
    out = result["execution_result"]
    assert out["type"] == "evaluate"
    # 标题 "Eco-friendly Water Bottle" 含 eco → 高分
    assert out["detail"]["title"] == 20
    # 5 条五点均短于 5 词 → 按规则为 0 分（规则本身如此，解析正常）
    assert out["detail"]["bullet_points"] == 0
    # 3 个关键词 × 4 = 12
    assert out["detail"]["keywords"] == 12


def test_parse_listing_handles_multi_line():
    """多行英文格式的解析兼容性"""
    text = "Title: Eco Friendly Bottle\nBullet Points:\n- Durable steel\n- Leak proof\nDescription: Great bottle for daily use.\nKeywords: eco, bottle"
    parsed = ev._parse_listing(text)
    assert parsed["title"] == "Eco Friendly Bottle"
    assert len(parsed["bullets"]) >= 2
    assert parsed["description"] != ""
    assert "eco" in parsed["keywords"]
