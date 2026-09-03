# -*- coding: utf-8 -*-
"""graph/state.py 测试：AgentState 结构与 add_messages 归约行为"""
from graph.state import AgentState, get_last_content
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage


def test_state_instantiate_with_dict_messages():
    state = AgentState(
        messages=[{"role": "user", "content": "hi"}],
        session_id="s1",
    )
    assert state["session_id"] == "s1"
    assert state["messages"][0]["content"] == "hi"
    # 可选字段默认 None
    assert state.get("intent") is None
    assert state.get("execution_result") is None
    assert state.get("error") is None
    assert state.get("uploaded_files") is None  # TypedDict 未给值时不存在


def test_add_messages_merges_dicts():
    """add_messages 会把 dict 消息转换为 BaseMessage 并追加"""
    merged = add_messages(
        [{"role": "user", "content": "a"}],
        {"role": "assistant", "content": "b"},
    )
    assert len(merged) == 2
    # langgraph 1.x 下 dict 被转换成 HumanMessage / AIMessage 对象
    from langchain_core.messages import BaseMessage

    assert all(isinstance(m, BaseMessage) for m in merged)


def test_add_messages_idempotent_for_same_ids():
    """同 id 消息重复追加时去重合并（add_messages 的规范行为）"""
    msg1 = {"role": "user", "content": "a", "id": "1"}
    msg2 = {"role": "user", "content": "a-2", "id": "1"}
    merged = add_messages([msg1], msg2)
    assert len(merged) == 1
    assert merged[0].content == "a-2"


def test_get_last_content_accepts_dict():
    """get_last_content 兼容 dict 形态消息"""
    state = {"messages": [{"role": "user", "content": "你好"}]}
    assert get_last_content(state) == "你好"


def test_get_last_content_accepts_base_message():
    """get_last_content 兼容 langgraph 1.x 归约后的 BaseMessage 对象"""
    state = {"messages": [HumanMessage(content="查询销售额")]}
    assert get_last_content(state) == "查询销售额"
