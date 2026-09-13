from entity import Tool
from models import LargeLanguageModel
from prompt import PromptModelHub, QwenModelPromptHub, create_prompt_hub

from utils import logger


class ToolSummaryHub:
    """
    ToolSummaryHub 类的初始化方法。

    参数:
        model (str): 使用的大语言模型名称。
        temperature (float): 控制生成文本随机性的温度参数，取值范围通常在 0 到 1 之间。
        top_p (float): 核采样的概率阈值，取值范围通常在 0 到 1 之间。

    属性:
        LargeLanguageModel (LargeLanguageModel): 大语言模型实例。
        PromptModelHub (PromptModelHub): 提示词模型中心实例。
        model (str): 使用的大语言模型名称。
        temperature (float): 控制生成文本随机性的温度参数。
        top_p (float): 核采样的概率阈值。
    """

    def __init__(self, model, temperature, top_p, api_url, api_key):
        self.LargeLanguageModel = LargeLanguageModel(api_url, api_key)
        self.PromptModelHub = create_prompt_hub(model)
        self.model = model
        self.temperature = temperature
        self.top_p = top_p

    def split_string_by_length(self, s, length):
        """
        将字符串 s 按照指定的长度 length 分割成多个子字符串，并返回一个列表。
        :param s: 要分割的字符串
        :param length: 每个子字符串的最大长度
        :return: 包含子字符串的列表
        """
        return [s[i:i + length] for i in range(0, len(s), length)]

    def summary_large_result(self, query, apis):
        flag = True
        for tmp in apis:
            if len(tmp["result"]) <= 100000:
                continue
            else:
                flag = False
        if flag:
            return apis
        else:
            for tmp in apis:
                if len(tmp["result"]) > 100000:
                    node_results = ""
                    api_description = tmp["tool"]
                    task_description = tmp["task_description"]
                    split_str_list = self.split_string_by_length(tmp["result"], 100000)
                    for chunk in split_str_list:
                        prompt = self.PromptModelHub.chunk_tool_summary_prompt(task_description=task_description,
                                                                               api_description=api_description,
                                                                               chunk_result=chunk)
                        model_output = self.LargeLanguageModel.chat_completions(prompt, self.model, self.temperature,
                                                                                self.top_p)
                        logger.info(model_output)
                        node_results += model_output
                    tmp["result"] = node_results
            return apis

    def tool_summary(self, query, apis):
        """
        生成工具摘要的函数。
            功能:
                根据输入的查询内容和 API 列表，生成对应的工具摘要。通过提示词模型生成提示词，
                再使用大语言模型生成最终的摘要内容。
            参数:
                query (str): 用户的查询内容。
                apis (list): API 执行列表，包括结果，用于生成工具摘要。
            返回值:
                str: 大语言模型生成的工具摘要内容。
            代码流程逻辑:
                1. 调用 PromptModelHub 实例的 gen_tool_summary_prompt 方法，根据查询内容和 API 列表生成提示词。
                2. 调用 LargeLanguageModel 实例的 chat_completions 方法，传入生成的提示词、模型名称、温度参数和核采样阈值，获取模型输出。
                3. 打印模型输出。
                4. 返回模型输出。
            """
        apis = self.summary_large_result(query, apis)
        prompt = self.PromptModelHub.gen_tool_summary_prompt(query, apis)
        model_output = self.LargeLanguageModel.chat_completions(prompt, self.model, self.temperature, self.top_p)
        logger.info(model_output)
        return model_output



