TASK_ERROR_CODE = 404
TASK_SUCCESS_CODE = 200

TASK_TYPE_UNKNOWN = -1 #任务初始化时的任务类型
TASK_TYPE_MAINTAIN = 0 #保持任务类型不变，更新任务数据时使用
TASK_TYPE_SINGLE = 1 #单API调用任务
TASK_TYPE_APIS = 2 #多API调用任务

TASK_STATUS_INIT = 0 #任务初始化，尚未运行
TASK_STATUS_RUNNING = 1 #任务正在运行
TASK_STATUS_WAIT_CONFIRM = 100 #任务等待人类确认
TASK_STATUS_FINISH = -1 #任务完成或中止

GRAPH_TITLE_SUCESS = "正常调用链"
GRAPH_TITLE_FAILURE = "异常调用链"
TASK_SYS_OUTPUT_STOP = "任务停止："

TASK_INIT_TOOL_ID = -1 #任务初始化时的工具ID

RESPONSE_STATUS_CODE_SUCCESS = 200
RESPONSE_STATUS_CODE_ERROR = 404
RESPONSE_AUTH_CODE_ERROR = 401
RESPONSE_ALLOW_CODE_ERROR = 403
# 人类反馈意图类型常量（方案 11）
INTENT_CONFIRM = "confirm"                 # 确认执行当前操作
INTENT_ABORT = "abort"                     # 终止任务
INTENT_CORRECT_PARAMS = "correct_params"   # 修改参数或约束
INTENT_CORRECT_TOOL = "correct_tool"       # 修改业务对象或工具
INTENT_CLARIFY = "clarify"                 # 提供缺失信息
INTENT_UNRELATED = "unrelated"             # 与当前确认无关
INTENT_UNCLEAR = "unclear"                 # 意图不明确（降级兜底）

# 全部有效意图集合
VALID_INTENTS = {
    INTENT_CONFIRM, INTENT_ABORT, INTENT_CORRECT_PARAMS,
    INTENT_CORRECT_TOOL, INTENT_CLARIFY, INTENT_UNRELATED, INTENT_UNCLEAR
}

DEFAULT_PERMISSIONS = ['login', 'logout', 'mesh_query', 'get_task_status']

