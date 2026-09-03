# -*- coding: utf-8 -*-
"""app.py 测试：在 stub 掉 Gradio 组件后验证 process_message / upload_file 逻辑

背景：当前环境 gradio 6.0.0 下 `gr.Blocks(theme=...)` 不兼容（真实导入会抛
TypeError），因此本文件先用 _Dummy 替换 gradio 组件后导入 app.py，
仅验证应用核心逻辑；Gradio 版本兼容性问题单独由 test_app_import_issue 记录。
"""
import sys
import pytest
import gradio as gr

_GRADIO_COMPONENTS = [
    "Blocks",
    "State",
    "Row",
    "Column",
    "Chatbot",
    "Textbox",
    "Button",
    "File",
    "Image",
    "Markdown",
    "themes",
]


class _Dummy:
    """通用 Gradio 组件替身：任何构造/方法调用均安全返回"""

    def __init__(self, *a, **kw):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __call__(self, *a, **kw):
        return self

    def __getattr__(self, name):
        return _Dummy()


@pytest.fixture(scope="module")
def app_module(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    for name in _GRADIO_COMPONENTS:
        mp.setattr(gr, name, _Dummy())

    import config as cfg

    tmp = tmp_path_factory.mktemp("appdb")
    mp.setattr(cfg, "DB_PATH", str(tmp / "test.db"))

    sys.modules.pop("app", None)
    import app

    yield app
    mp.undo()


# ---------- Gradio 版本兼容性（修复后） ----------

def test_app_imports_under_gradio6(tmp_path, monkeypatch):
    """修复后：当前环境 gradio 6.0.0 下 app.py 可直接导入
    （Blocks 的 theme 参数已按版本做兼容处理）。"""
    import gradio as _gr
    import config as _cfg

    monkeypatch.setattr(_cfg, "DB_PATH", str(tmp_path / "test.db"))
    sys.modules.pop("app", None)

    import app

    assert app.demo is not None
    assert _gr.__version__  # 保证断言的是当前真实版本


# ---------- process_message ----------

def test_process_message_data_type(app_module, monkeypatch):
    class FakeWorkflow:
        def invoke(self, state):
            return {
                "execution_result": {
                    "type": "data",
                    "summary": "销售额环比增长 20%",
                    "chart": None,
                    "sql": "SELECT date, sales FROM file_x",
                    "dataframe": [
                        {"date": "2026-07-01", "sales": 100},
                        {"date": "2026-07-02", "sales": 150},
                    ],
                    "total_rows": 2,
                    "answer_type": "summary",
                },
                "intent": "data",
            }

    monkeypatch.setattr(app_module, "workflow", FakeWorkflow())
    reply, state = app_module.process_message("查询销售额", None, None)
    assert "销售额环比增长 20%" in reply
    assert "SELECT date, sales" in reply
    # Markdown 表格展示查询结果
    assert "| date" in reply
    assert "2026-07-01" in reply
    assert state["session_id"]  # 自动生成会话 ID
    assert state["messages"][-1]["role"] == "assistant"


def test_process_message_listing_type(app_module, monkeypatch):
    class FakeWorkflow:
        def invoke(self, state):
            return {
                "execution_result": {
                    "type": "listing",
                    "listings": [
                        {
                            "style": "专业严谨型",
                            "raw": "Title: Eco Bottle",
                            "filtered_html": "Title: <span>Eco</span> Bottle",
                            "has_issue": True,
                            "hits": ["best"],
                        }
                    ],
                },
                "intent": "listing",
            }

    monkeypatch.setattr(app_module, "workflow", FakeWorkflow())
    reply, _ = app_module.process_message("生成Listing", None, None)
    assert "专业严谨型" in reply
    assert "敏感词" in reply
    assert "best" in reply


def test_process_message_image_type(app_module, monkeypatch):
    class FakeWorkflow:
        def invoke(self, state):
            return {
                "execution_result": {
                    "type": "image",
                    "images": [
                        {"style": "正面视角", "scene": "户外背景", "url": "http://example.com/a.png"}
                    ],
                },
                "intent": "image",
            }

    monkeypatch.setattr(app_module, "workflow", FakeWorkflow())
    reply, _ = app_module.process_message("生成图片", None, None)
    assert "正面视角 + 户外背景" in reply
    assert '<img src="http://example.com/a.png"' in reply


def test_process_message_evaluate_type(app_module, monkeypatch):
    class FakeWorkflow:
        def invoke(self, state):
            return {
                "execution_result": {
                    "type": "evaluate",
                    "score": 85,
                    "detail": {"title": 18, "bullet_points": 16, "description": 17, "keywords": 18, "image_quality": 16},
                    "suggestions": ["标题加关键词", "补全五点", "增加图片"],
                },
                "intent": "evaluate",
            }

    monkeypatch.setattr(app_module, "workflow", FakeWorkflow())
    reply, _ = app_module.process_message("评估Listing", None, None)
    assert "综合评分：85/100" in reply
    assert "标题加关键词" in reply


def test_process_message_unknown_type(app_module, monkeypatch):
    class FakeWorkflow:
        def invoke(self, state):
            return {"execution_result": {"type": "unknown"}, "intent": "whatever"}

    monkeypatch.setattr(app_module, "workflow", FakeWorkflow())
    reply, _ = app_module.process_message("随便聊聊", None, None)
    assert "暂未识别您的意图" in reply


def test_process_message_with_empty_dict_state(app_module, monkeypatch):
    """Gradio gr.State({}) 初始值是空 dict 而非 None，
    应同样触发会话初始化（回归：修复 KeyError: 'session_id'）"""
    class FakeWorkflow:
        def invoke(self, state):
            return {"execution_result": {"type": "unknown"}, "intent": "x"}

    monkeypatch.setattr(app_module, "workflow", FakeWorkflow())
    reply, state = app_module.process_message("查询数据", None, {})
    assert "暂未识别您的意图" in reply
    assert state["session_id"]  # 空 dict 也应初始化出 session_id


def test_process_message_workflow_exception_fallback(app_module, monkeypatch):
    """回归：workflow.invoke 抛异常时返回友好提示，不中断前端连接
    （此前异常冒泡到 Gradio 导致 ERR_ABORTED）"""
    class BoomWorkflow:
        def invoke(self, state):
            raise ValueError("仅支持 SELECT / WITH 查询")

    monkeypatch.setattr(app_module, "workflow", BoomWorkflow())
    reply, state = app_module.process_message("查询数据", None, None)
    assert "处理失败" in reply
    assert "ValueError" in reply
    assert state["session_id"]


def test_process_message_keeps_session(app_module, monkeypatch):
    """同一 session_state 再次调用时复用 session_id，不重复生成"""
    class FakeWorkflow:
        def invoke(self, state):
            return {"execution_result": {"type": "unknown"}, "intent": "x"}

    monkeypatch.setattr(app_module, "workflow", FakeWorkflow())
    _, state = app_module.process_message("第一次", None, None)
    sid = state["session_id"]
    _, state2 = app_module.process_message("第二次", None, state)
    assert state2["session_id"] == sid
    assert len(state2["messages"]) == 4  # user/assistant × 2 轮


# ---------- upload_file ----------

def test_upload_file(app_module, monkeypatch):
    class FakeFile:
        name = "C:/tmp/sales.csv"

    monkeypatch.setattr(
        app_module.db_manager,
        "upload_file",
        lambda sid, path, name: "file_abc123",
    )
    status, state = app_module.upload_file(FakeFile(), None)
    assert "file_abc123" in status
    assert state["uploaded_files"] == ["file_abc123"]


def test_upload_file_with_empty_dict_state(app_module, monkeypatch):
    """Gradio gr.State({}) 初始值是空 dict，上传同样要能初始化会话
    （回归：修复 KeyError: 'session_id'）"""
    class FakeFile:
        name = "C:/tmp/sales.csv"

    monkeypatch.setattr(
        app_module.db_manager,
        "upload_file",
        lambda sid, path, name: "file_abc123",
    )
    status, state = app_module.upload_file(FakeFile(), {})
    assert "file_abc123" in status
    assert state["session_id"]
    assert state["uploaded_files"] == ["file_abc123"]


def test_upload_image(app_module):
    """产品图片上传：写入 current_image_url 供 Listing/场景图使用"""
    status, state = app_module.upload_image("C:/tmp/product.png", None)
    assert "产品图片已上传" in status
    assert state["current_image_url"] == "C:/tmp/product.png"


def test_upload_image_with_existing_session(app_module):
    """已存在会话时更新图片不丢失其他字段"""
    session = {"session_id": "s1", "messages": [], "uploaded_files": ["file_x"], "current_image_url": None}
    _, state = app_module.upload_image("C:/tmp/img2.png", session)
    assert state["session_id"] == "s1"
    assert state["current_image_url"] == "C:/tmp/img2.png"
    assert state["uploaded_files"] == ["file_x"]
