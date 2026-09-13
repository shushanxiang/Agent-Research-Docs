"""
Prompt 版本注册表。

版本号的源头在 Prompt 类的常量中（general_prompts.py / qwen_model_prompts.py）。
此文件只做读取和组装，不手动写死版本号。

评估体系的 eval runner 通过 get_prompt_version_snapshot() 自动获取版本快照。
"""

from prompt.general_prompts import PromptModelHub
from prompt.qwen_model_prompts import QwenModelPromptHub


def get_prompt_version_snapshot() -> dict:
    """
    从 Prompt 类的常量中读取当前全部版本号，组装为快照。

    评估报告和 eval runner 调用此函数，无需手动维护字典。
    """
    base = PromptModelHub
    qwen = QwenModelPromptHub

    return {
        # ----- 通用 Prompt（prompt/general_prompts.py）-----
        "root_task": {
            "version": base.VERSION_ROOT_TASK,
            "class": "PromptModelHub",
            "file": "prompt/general_prompts.py",
            "description": "判断单任务/多任务",
        },
        "subtask_context": {
            "version": base.VERSION_SUBTASK_CONTEXT,
            "class": "PromptModelHub",
            "file": "prompt/general_prompts.py",
            "description": "基于上下文生成子任务",
        },
        "tool_selection": {
            "version": base.VERSION_TOOL_SELECTION,
            "class": "PromptModelHub",
            "file": "prompt/general_prompts.py",
            "description": "从候选工具中选择最佳工具",
        },
        "param_task": {
            "version": base.VERSION_PARAM_TASK,
            "class": "PromptModelHub",
            "file": "prompt/general_prompts.py",
            "description": "生成参数补全的描述词",
        },
        "param_extraction": {
            "version": base.VERSION_PARAM_EXTRACTION,
            "class": "PromptModelHub",
            "file": "prompt/general_prompts.py",
            "description": "从 query 中提取 API 参数",
        },
        "tool_summary": {
            "version": base.VERSION_TOOL_SUMMARY,
            "class": "PromptModelHub",
            "file": "prompt/general_prompts.py",
            "description": "API 执行结果摘要",
        },
        "chunk_summary": {
            "version": base.VERSION_CHUNK_SUMMARY,
            "class": "PromptModelHub",
            "file": "prompt/general_prompts.py",
            "description": "大数据分片摘要",
        },
        "injection_judge": {
            "version": base.VERSION_INJECTION_JUDGE,
            "class": "PromptModelHub",
            "file": "prompt/general_prompts.py",
            "description": "注入攻击检测",
        },
        "intent_recognition": {
            "version": base.VERSION_INTENT_RECOGNITION,
            "class": "PromptModelHub",
            "file": "prompt/general_prompts.py",
            "description": "人类反馈意图识别（方案 11）",
        },

        # ----- Qwen 专用 Prompt 覆盖（prompt/qwen_model_prompts.py）-----
        # 仅列出 Qwen 类实际 override 的方法，未覆盖的继承父类版本号
        "qwen_root_task": {
            "version": qwen.VERSION_QWEN_ROOT_TASK,
            "class": "QwenModelPromptHub",
            "file": "prompt/qwen_model_prompts.py",
            "description": "千问专用：判断单任务/多任务 prompt 覆盖（覆盖父类 root_task）",
        },
        "qwen_param_task": {
            "version": qwen.VERSION_QWEN_PARAM_TASK,
            "class": "QwenModelPromptHub",
            "file": "prompt/qwen_model_prompts.py",
            "description": "千问专用：参数补全描述词 prompt 覆盖（覆盖父类 param_task）",
        },
        "qwen_subtask_context": {
            "version": qwen.VERSION_QWEN_SUBTASK_CONTEXT,
            "class": "QwenModelPromptHub",
            "file": "prompt/qwen_model_prompts.py",
            "description": "千问专用：子任务上下文 prompt 覆盖（覆盖父类 subtask_context）",
        },
        "qwen_param_extraction": {
            "version": qwen.VERSION_QWEN_PARAM_EXTRACTION,
            "class": "QwenModelPromptHub",
            "file": "prompt/qwen_model_prompts.py",
            "description": "千问专用：参数提取 prompt 覆盖（覆盖父类 param_extraction）",
        },

        # ----- 模型配置 -----
        "model_config": {
            "version": "v1.0",
            "class": "N/A",
            "file": "utils/config.py",
            "description": "模型 model_name / temperature / top_p 配置",
        },
    }
