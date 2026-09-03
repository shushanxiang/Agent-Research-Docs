# -*- coding: utf-8 -*-
"""utils/llm_client.py 测试：mock dashscope 验证 call_llm / call_vl 的成功、失败与重试逻辑"""
import types
import pytest
import dashscope
from utils import llm_client


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeOutput:
    def __init__(self, content, vl=False):
        if vl:
            # MultiModalConversation 的 content 是 [{"text": ...}]
            self.choices = [types.SimpleNamespace(message=types.SimpleNamespace(content=[{"text": content}]))]
        else:
            self.choices = [types.SimpleNamespace(message=FakeMessage(content))]


class FakeResp:
    def __init__(self, status_code=200, content="ok", message=None, code=None, vl=False):
        self.status_code = status_code
        self.message = message
        self.code = code
        self.output = FakeOutput(content, vl=vl) if status_code == 200 else None


def test_call_llm_success(monkeypatch):
    monkeypatch.setattr(dashscope.Generation, "call", staticmethod(lambda **kw: FakeResp(200, "你好")))
    assert llm_client.call_llm("问题") == "你好"


def test_call_llm_system_prompt_passed(monkeypatch):
    seen = {}

    def fake_call(**kw):
        seen["messages"] = kw.get("messages")
        return FakeResp(200, "ok")

    monkeypatch.setattr(dashscope.Generation, "call", staticmethod(fake_call))
    llm_client.call_llm("问题", system_prompt="你是助手")
    assert seen["messages"][0]["role"] == "system"


def test_call_llm_temperature_passed(monkeypatch):
    """temperature 参数应透传给 API（意图识别等分类任务用低值）"""
    seen = {}

    def fake_call(**kw):
        seen["temperature"] = kw.get("temperature")
        return FakeResp(200, "ok")

    monkeypatch.setattr(dashscope.Generation, "call", staticmethod(fake_call))
    llm_client.call_llm("问题", temperature=0.1)
    assert seen["temperature"] == 0.1


def test_call_llm_api_error_returns_fallback(monkeypatch):
    """API 返回非 200：重试耗尽后返回 'LLM调用失败' 字符串（不抛异常，保证链路不崩）"""
    monkeypatch.setattr(
        dashscope.Generation,
        "call",
        staticmethod(lambda **kw: FakeResp(500, message="server error", code="500")),
    )
    result = llm_client.call_llm("问题")
    assert result.startswith("LLM调用失败")


def test_call_llm_exception_retries(monkeypatch):
    """连续抛异常：重试后返回兜底字符串"""
    calls = {"n": 0}

    def boom(**kw):
        calls["n"] += 1
        raise RuntimeError("network down")

    monkeypatch.setattr(dashscope.Generation, "call", staticmethod(boom))
    result = llm_client.call_llm("问题", max_retries=2)
    assert calls["n"] == 3  # 1 次 + 2 次重试
    assert result.startswith("LLM调用失败")


def test_call_vl_success(monkeypatch):
    monkeypatch.setattr(
        dashscope.MultiModalConversation,
        "call",
        staticmethod(lambda **kw: FakeResp(200, "蓝色塑料瓶", vl=True)),
    )
    assert llm_client.call_vl("http://img", "描述") == "蓝色塑料瓶"


def test_call_vl_failure_raises(monkeypatch):
    monkeypatch.setattr(
        dashscope.MultiModalConversation,
        "call",
        staticmethod(lambda **kw: FakeResp(500, message="err")),
    )
    with pytest.raises(Exception, match="VL Error"):
        llm_client.call_vl("http://img", "描述")
