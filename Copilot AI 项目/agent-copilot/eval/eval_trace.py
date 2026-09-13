"""
评估 Trace 数据模型

从现有 Task 实体 + 日志中采集结构化 Trace，
将分散的日志信息聚合为 AgentTrace。
"""

from dataclasses import dataclass, field
from typing import Any, Optional
import json


@dataclass
class LLMCallRecord:
    """单次 LLM 调用"""
    step_name: str
    model_id: str
    prompt: str
    response: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cache_hit: bool = False
    timestamp_ms: float = 0.0
    first_token_timestamp_ms: Optional[float] = None


@dataclass
class ToolCallRecord:
    """单次工具调用 — 动作型 Agent 的核心 trace"""
    step_name: str
    tool_name: str
    params: dict = field(default_factory=dict)
    result: Any = None
    result_summary: str = ""
    latency_ms: int = 0
    cost: float = 0.0
    error: Optional[str] = None
    retry_count: int = 0
    timestamp_ms: float = 0.0
    confirmed_by_user: bool = False


@dataclass
class AgentTrace:
    """一次完整的 Agent 任务执行记录"""
    run_id: str
    session_id: str
    test_case_id: str
    task_input: str
    task_output: str
    task_success: Optional[bool] = None
    goal_achievement_score: Optional[int] = None
    final_status: Optional[str] = None
    error_type: Optional[str] = None
    stop_reason: Optional[str] = None       # param_incomplete / param_invalid / injection_blocked / tool_not_found
    start_time_ms: float = 0.0
    end_time_ms: float = 0.0

    llm_calls: list[LLMCallRecord] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    intermediate_outputs: dict = field(default_factory=dict)
    feedback_log: list = field(default_factory=list)  # HITL 反馈审计日志


# ===== 从现有系统中采集 Trace 的适配器 =====

def _int_tool_id_to_model(curr_tool_id, tool_id_map: dict = None) -> str:
    """将整数 tool_id 转为 name_for_model。

    优先使用 tool_id_map（{内部ID: name_for_model}）映射，
    兜底回退为 tool{id} 格式（适用于旧版连续编号场景）。
    """
    if curr_tool_id and curr_tool_id > 0:
        if tool_id_map:
            mapped = tool_id_map.get(int(curr_tool_id))
            if mapped:
                return mapped
        return f"tool{curr_tool_id}"
    return ""


def _detect_injection_rejected(system_output: str) -> bool:
    """检测 Agent 是否因检测到注入攻击而拒绝执行"""
    injection_keywords = ["提示注入攻击"]
    if system_output:
        return any(kw in system_output for kw in injection_keywords)
    return False


def _detect_param_rejected(system_output: str) -> bool:
    """检测 Agent 是否因参数校验不通过而拒绝"""
    if system_output:
        return "参数校验不通过" in system_output
    return False


def _detect_stop_reason(system_output: str) -> Optional[str]:
    """从 system_output 中检测 Agent 停止原因"""
    if not system_output:
        return None
    if "参数校验不通过" in system_output or "非法参数" in system_output:
        return "param_invalid"
    if "无法为" in system_output and ("补全缺少参数" in system_output or "完全缺少参数" in system_output):
        return "param_incomplete"
    if "未找到合适的工具" in system_output:
        return "tool_not_found"
    if "提示注入攻击" in system_output:
        return "injection_blocked"
    return None


def collect_trace_from_task(task, llm_call_logs: list = None, name_mapping: dict = None, tool_id_map: dict = None) -> AgentTrace:
    """
    从现有 Task 实体 + 日志中采集结构化 Trace。

    ApiPlanningHub 执行完成后调用此函数，将分散的日志信息聚合为 AgentTrace。
    优先从 task.nodes 采集；nodes 为空时回退到 curr_tool_id + curr_tool_param。

    Args:
        task: Task 实体（mongoengine Document），包含 nodes/edges/system_output 等字段
        llm_call_logs: 可选的 LLMCallRecord 列表（由 tracing.py 采集）
        name_mapping: name_for_human → name_for_model 映射字典
        tool_id_map: {tool.tool_id: name_for_model} 映射字典，用于将 Milvus 内部 ID 转为 name_for_model

    Returns:
        AgentTrace: 结构化的执行记录
    """
    if name_mapping is None:
        name_mapping = {}

    system_output = task.system_output or ""
    task_status = task.status

    # 判断最终状态
    if task_status == -1:
        final_status = "completed"
    elif task_status == 100:
        final_status = "waiting_confirmation"
    else:
        final_status = "failed"

    if "任务停止" in system_output:
        final_status = "cancelled"

    # 检测停止原因
    stop_reason = _detect_stop_reason(system_output)

    trace = AgentTrace(
        run_id=task.task_id or "",
        session_id=task.task_id or "",
        test_case_id="",
        task_input=task.raw_query or "",
        task_output=system_output,
        stop_reason=stop_reason,
        task_success=(task_status == -1 and "任务停止" not in system_output),
        final_status=final_status,
    )

    # 采集 HITL 反馈审计日志（方案 11 写入的 feedback_log）
    if hasattr(task, 'feedback_log') and task.feedback_log:
        trace.feedback_log = list(task.feedback_log)

    has_nodes = bool(task.nodes)
    tool_calls_from_nodes = 0

    # 优先从 task.nodes 恢复工具调用记录
    if has_nodes:
        for node in task.nodes:
            params = {}
            try:
                raw_params = node.get("params", "{}")
                if isinstance(raw_params, str):
                    params = json.loads(raw_params)
                elif isinstance(raw_params, dict):
                    params = raw_params
            except (json.JSONDecodeError, TypeError):
                params = {}

            # nodes 中的 params 可能被 tool_use 原地修改为空（如 GET 路径参数被消费），
            # 回退到 task.curr_tool_param 获取完整参数
            if not params and task.curr_tool_param:
                params = dict(task.curr_tool_param)

            result = node.get("result", "")
            label = node.get("label", "")

            # 将 name_for_human 映射为 name_for_model，与测试用例 expected_tools 对齐
            tool_name_mapped = name_mapping.get(label, label)

            trace.tool_calls.append(ToolCallRecord(
                step_name=node.get("task_description", ""),
                tool_name=tool_name_mapped,
                params=params,
                result=result,
                result_summary=str(result)[:200] if result else "",
                error=None if "异常" not in str(label) else str(label),
                confirmed_by_user=True,  # 能写入 node 说明已通过人类确认流程
            ))
            tool_calls_from_nodes += 1

    # nodes 为空时，从 curr_tool_id + curr_tool_param 恢复工具调用
    if tool_calls_from_nodes == 0 and task.curr_tool_id and task.curr_tool_id > 0:
        tool_name = _int_tool_id_to_model(task.curr_tool_id, tool_id_map)
        params = task.curr_tool_param or {}
        # 判断异常类型
        error = None
        if _detect_injection_rejected(system_output):
            error = "Agent 检测到提示注入攻击，已拒绝执行"
        elif _detect_param_rejected(system_output):
            error = "Agent 参数校验不通过"
        elif task_status == -1 and "任务停止" in system_output:
            error = "任务因缺少必要参数或异常而停止"

        trace.tool_calls.append(ToolCallRecord(
            step_name=task.curr_task_desc or "",
            tool_name=tool_name,
            params=params,
            result=system_output[:500] if system_output else "",
            result_summary=system_output[:200] if system_output else "",
            error=error,
            confirmed_by_user=(task_status == -1),
        ))

    # 合并 LLM 调用记录
    if llm_call_logs:
        trace.llm_calls.extend(llm_call_logs)

    return trace


def extract_tool_names_from_task(task) -> list:
    """从 Task 的 nodes 中提取工具名称序列（用于路径稳定性分析）"""
    tool_names = []
    for node in (task.nodes or []):
        label = node.get("label", "")
        if label and "异常" not in str(label):
            tool_names.append(label)
    return tool_names
