# -*- coding: utf-8 -*-
"""graph/image_agent.py 测试：mock dashscope ImageSynthesis 成功与失败分支"""
import time
import graph.image_agent as ia
from conftest import make_state


class FakeResult:
    def __init__(self, url):
        self.url = url


class FakeOutput:
    def __init__(self):
        self.results = [FakeResult("http://example.com/img1.png")]


class FakeRespOK:
    status_code = 200
    output = FakeOutput()


class FakeRespErr:
    status_code = 500
    message = "rate limit"
    output = None


def _run(monkeypatch, resp):
    monkeypatch.setattr(ia.ImageSynthesis, "call", staticmethod(lambda **kw: resp))
    monkeypatch.setattr(time, "sleep", lambda s: None)  # 加速测试
    state = make_state([{"role": "user", "content": "生成产品场景图"}])
    return ia.image_agent_node(state)


def test_image_agent_success(monkeypatch):
    result = _run(monkeypatch, FakeRespOK())
    out = result["execution_result"]
    assert out["type"] == "image"
    assert len(out["images"]) == 4  # 2 角度 × 2 场景
    for img in out["images"]:
        assert img["style"] and img["scene"]
        assert img["url"].startswith("http://")


def test_image_agent_api_error_fallback(monkeypatch):
    result = _run(monkeypatch, FakeRespErr())
    out = result["execution_result"]
    assert all("生成失败" in img["url"] for img in out["images"])


def test_image_agent_exception_fallback(monkeypatch):
    def boom(**kw):
        raise ConnectionError("timeout")

    monkeypatch.setattr(ia.ImageSynthesis, "call", staticmethod(boom))
    monkeypatch.setattr(time, "sleep", lambda s: None)
    state = make_state([{"role": "user", "content": "生成产品场景图"}])
    result = ia.image_agent_node(state)
    out = result["execution_result"]
    assert all("异常" in img["url"] for img in out["images"])
