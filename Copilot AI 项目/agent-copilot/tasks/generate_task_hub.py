from typing import List

from entity import Tool
from models import LargeLanguageModel
from prompt import PromptModelHub, QwenModelPromptHub, create_prompt_hub
from tools import ToolManager
from utils import logger
import traceback

class GenerateTaskHub:
    """
    GenerateTaskHub 类用于生成任务的核心类，负责各种任务执行。

    __init__ 方法用于初始化 GenerateTaskHub 实例。

    参数:
        model (str): 使用的语言模型名称。
        temperature (float): 控制生成文本的随机性，值越大输出越随机。
        top_p (float): 核采样的概率阈值，用于控制生成文本的多样性。

    属性:
        LargeLanguageModel (LargeLanguageModel): 大语言模型实例，用于生成文本。
        PromptModelHub (PromptModelHub): 提示词模型中心实例，用于生成各种提示词。
        model (str): 使用的语言模型名称。
        temperature (float): 控制生成文本的随机性参数。
        top_p (float): 核采样的概率阈值。
    """

    def __init__(self, model, temperature, top_p, api_url, api_key, mongo_host, mongo_db, mongo_port, milvus_uri, milvus_db_name):
        self.LargeLanguageModel = LargeLanguageModel(api_url, api_key)
        self.PromptModelHub = create_prompt_hub(model)
        self.ToolManager = ToolManager(mongo_host, mongo_db, mongo_port, milvus_uri, milvus_db_name)
        self.model = model
        self.temperature = temperature
        self.top_p = top_p


    def gen_root_task(self, query):
        """
        生成根任务的描述信息。
        代码流程逻辑:
        1. 调用 PromptModelHub 实例的 gen_root_task_prompt 方法，根据输入的查询词生成根任务的提示词。
        2. 打印生成的提示词，方便调试查看。
        3. 打印分隔线，提高输出的可读性。
        4. 调用 LargeLanguageModel 实例的 chat_completions 方法，根据提示词、模型名称、随机性参数和核采样阈值生成任务描述。
        5. 打印生成的任务描述，方便调试查看。
        6. 打印分隔线，提高输出的可读性。
        7. 调用 PromptModelHub 实例的 post_process_gen_root_task 方法对生成的任务描述进行后处理。
        8. 返回后处理后的是否为单任务标识和任务描述。
        参数:
            query (str): 输入的查询词，用于生成根任务。
        返回:
            tuple: 包含两个元素的元组，第一个元素 isSingleTask 为布尔值，表示是否为单任务；
            第二个元素 task_description 为字符串，表示生成的任务描述。
        """
        # 获取所有工具
        tools = self.ToolManager.get_raw_all_tools()
        prompt = self.PromptModelHub.gen_root_task_prompt(query, tools)
        task_description = self.LargeLanguageModel.chat_completions(prompt, self.model, self.temperature, self.top_p)
        isSingleTask, task_description = self.PromptModelHub.post_process_gen_root_task(task_description)
        return isSingleTask, task_description


    def gen_param_task(self, query, params, missing_params):
        """
        产生参数生成或补齐任务的描述词
        代码流程逻辑:
        1. 调用 PromptModelHub 实例的 gen_param_task_prompt 方法，根据输入的查询词、参数和缺失参数生成带参数任务的提示词。
        2. 调用 LargeLanguageModel 实例的 chat_completions 方法，根据提示词、模型名称、随机性参数和核采样阈值生成任务描述。
        3. 返回生成的任务描述。
        参数:
            query (str): 输入的查询词，用于生成任务。
            params (dict): 已有的参数信息。
            missing_params (list): 缺失的参数列表。
        返回:
            str: 参数生成或补齐任务的描述词。
        """
        prompt = self.PromptModelHub.gen_param_task_prompt(query, params, missing_params)
        task_description = self.LargeLanguageModel.chat_completions(prompt, self.model, self.temperature, self.top_p)
        return task_description


    def gen_from_context_task(self, query, apis):
        """
        基于上下文生成子任务的描述信息。
        代码流程逻辑:
        1. 调用 PromptModelHub 实例的 gen_subtask_context_prompt 方法，根据输入的查询词和 API 列表生成子任务的提示词。
        2. 打印生成的提示词，方便调试查看。
        3. 调用 LargeLanguageModel 实例的 chat_completions 方法，根据提示词、模型名称、随机性参数和核采样阈值生成任务描述。
        4. 调用 PromptModelHub 实例的 post_process_gen_subtask_task 方法对生成的任务描述进行后处理。
        5. 返回后处理后的标识和任务描述。
        参数:
            query (str): 输入的查询词，用于生成子任务。
            apis (list): API 列表，作为生成子任务的上下文信息。
        返回:
            tuple: 包含两个元素的元组，第一个元素 flag 为布尔值或其他标识；
            第二个元素 task_description 为字符串，表示生成的子任务描述。
        """
        prompt = self.PromptModelHub.gen_subtask_context_prompt(query, apis)
        task_description = self.LargeLanguageModel.chat_completions(prompt, self.model, self.temperature, self.top_p)
        flag, task_description = self.PromptModelHub.post_process_gen_subtask_task(task_description)
        logger.info(f"基于上下文生成子任务的描述信息{query}结果为：{flag},{task_description}")
        return flag, task_description

    def gen_context_request_task(self, contexts):
        prompt = self.PromptModelHub.gen_context_request(contexts)
        user_request = self.LargeLanguageModel.chat_completions(prompt, self.model, self.temperature,
                                                                self.top_p)
        return user_request

    def gen_judge_task(self, query, tool: Tool, requestBody: dict):
        if not tool.isValidate:
            return False, None
        else:
            prompt = self.PromptModelHub.judge_validate(query, tool, requestBody)
            judge_result = self.LargeLanguageModel.chat_completions(prompt, self.model, self.temperature,
                                                                    self.top_p)
            flag, reason = self.PromptModelHub.post_process_gen_judge_task(judge_result)
            return flag, reason

