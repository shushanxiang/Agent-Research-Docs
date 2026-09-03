import os


def _read_machine_env(name: str) -> str:
    """读取 Windows 系统级环境变量（Machine，注册表）。非 Windows 或读取失败返回空串。"""
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return value if isinstance(value, str) else ""
    except Exception:
        return ""


def _get_env(name: str) -> str:
    """按优先级获取环境变量：系统级(Machine) → 当前进程环境(含用户级)。"""
    machine = _read_machine_env(name)
    if machine:
        return machine
    return os.environ.get(name, "")


# 通义千问配置：从系统环境变量获取（未配置则为空，调用时给出明确提示）
DASHSCOPE_API_KEY = _get_env("DASHSCOPE_API_KEY")

# 模型映射（文本：DeepSeek V4 Flash，免费额度；多模态/文生图：通义千问）
LLM_MODEL_NAME = "deepseek-v4-flash-0731"   # 免费、快，适合意图识别和轻量生成
VL_MODEL_NAME = "qwen-vl-plus"         # 多模态看图
IMAGE_GEN_MODEL = "wanx-v1"            # 通义万相文生图

# 敏感词文件路径
SENSITIVE_WORDS_FILE = "utils/forbidden_words.txt"

# DuckDB 持久化路径
DB_PATH = "data/warehouse.db"

# 图片生成参数（成本控制：≤$0.05/张）
IMAGE_GEN_CONFIG = {
    "width": 512,
    "height": 512,
    "steps": 20,          # 步数越少越快，通义万相可能不支持steps，会忽略
    "n": 4,               # 单次批量生成4张，减少调用次数（通义万相batch限制查看文档）
}