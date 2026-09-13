"""测试循环检测（覆盖 P0-04，增强版 4 维检测）"""

import pytest
from conftest import MockTask


def _invoke_validate(task, cur_result, max_steps=15):
    """调用 _not_loop_validate 方法"""
    from apis.api_planning_hub import ApiPlanningHub
    # 创建一个最小化的实例来调用该方法
    hub = ApiPlanningHub.__new__(ApiPlanningHub)
    return ApiPlanningHub._not_loop_validate(hub, task, cur_result, max_steps)


class TestLoopDetection:
    """循环检测四维测试"""

    def test_signature_repeat(self):
        """状态签名重复：同一工具 + 同一结果在 4 次窗口中出现 3 次"""
        task = MockTask(nodes=[
            {"label": "queryOrders", "result": "[]", "params": "{}"},
            {"label": "queryOrders", "result": "[]", "params": "{}"},
            {"label": "toolB", "result": "other", "params": "{}"},
        ])
        cur_result = {"tool": "queryOrders", "result": "[]"}
        is_ok = _invoke_validate(task, cur_result)
        assert is_ok is False

    def test_gradient_loop(self):
        """参数梯度循环：连续 3 次同一工具（不同结果）"""
        task = MockTask(nodes=[
            {"label": "queryOrders", "result": "r1", "params": '{"offset": 0}'},
            {"label": "queryOrders", "result": "r2", "params": '{"offset": 1}'},
        ])
        cur_result = {"tool": "queryOrders", "result": "r3", "param": {"offset": 2}}
        is_ok = _invoke_validate(task, cur_result)
        assert is_ok is False

    def test_tool_chain_cycle_2(self):
        """工具链环路：A→B→A→B 周期=2"""
        task = MockTask(nodes=[
            {"label": "toolA", "result": "r1", "params": "{}"},
            {"label": "toolB", "result": "r2", "params": "{}"},
            {"label": "toolA", "result": "r3", "params": "{}"},
        ])
        cur_result = {"tool": "toolB", "result": "r4"}
        is_ok = _invoke_validate(task, cur_result)
        assert is_ok is False

    def test_tool_chain_cycle_3(self):
        """工具链环路：A→B→C→A→B→C 周期=3"""
        task = MockTask(nodes=[
            {"label": "toolA", "result": "r1", "params": "{}"},
            {"label": "toolB", "result": "r2", "params": "{}"},
            {"label": "toolC", "result": "r3", "params": "{}"},
            {"label": "toolA", "result": "r4", "params": "{}"},
            {"label": "toolB", "result": "r5", "params": "{}"},
        ])
        cur_result = {"tool": "toolC", "result": "r6"}
        is_ok = _invoke_validate(task, cur_result)
        assert is_ok is False

    def test_max_steps_exceeded(self):
        """步数预算：nodes 数量 >= max_steps 应被拒绝"""
        nodes = [{"label": f"tool{i}", "result": f"r{i}", "params": "{}"} for i in range(15)]
        task = MockTask(nodes=nodes)
        cur_result = {"tool": "tool16", "result": "r16"}
        is_ok = _invoke_validate(task, cur_result)
        assert is_ok is False

    def test_normal_no_loop(self):
        """正常无循环场景应通过"""
        task = MockTask(nodes=[
            {"label": "toolA", "result": "r1", "params": "{}"},
            {"label": "toolB", "result": "r2", "params": "{}"},
        ])
        cur_result = {"tool": "toolC", "result": "r3"}
        is_ok = _invoke_validate(task, cur_result)
        assert is_ok is True

    def test_single_call_no_loop(self):
        """单次调用无循环"""
        task = MockTask(nodes=[])
        cur_result = {"tool": "toolA", "result": "r1"}
        is_ok = _invoke_validate(task, cur_result)
        assert is_ok is True

    def test_two_same_tool_different_result_no_loop(self):
        """同一工具 2 次但结果不同，不触发梯度检测"""
        task = MockTask(nodes=[
            {"label": "toolA", "result": "r1", "params": "{}"},
        ])
        cur_result = {"tool": "toolA", "result": "r2"}
        is_ok = _invoke_validate(task, cur_result)
        assert is_ok is True  # 只有 2 次，梯度检测需要 3 次

    def test_custom_max_steps(self):
        """自定义步数预算：nodes 已有 3 条，max_steps=3 时触发"""
        task = MockTask(nodes=[
            {"label": "tool1", "result": "r1", "params": "{}"},
            {"label": "tool2", "result": "r2", "params": "{}"},
            {"label": "tool3", "result": "r3", "params": "{}"},
        ])
        cur_result = {"tool": "tool4", "result": "r4"}
        is_ok = _invoke_validate(task, cur_result, max_steps=3)
        assert is_ok is False  # nodes(3) >= max_steps(3)

    def test_json_parse_error_handled(self):
        """params 字段 JSON 解析异常时被安全处理"""
        task = MockTask(nodes=[
            {"label": "toolA", "result": "r1", "params": "not valid json!!!"},
            {"label": "toolB", "result": "r2", "params": "{}"},
        ])
        cur_result = {"tool": "toolC", "result": "r3"}
        is_ok = _invoke_validate(task, cur_result)
        assert is_ok is True
