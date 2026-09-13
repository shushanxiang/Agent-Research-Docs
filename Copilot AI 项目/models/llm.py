import time
from utils.function_util import timing_decorator
import random
from utils import logger
import traceback
import time
from utils.function_util import timing_decorator
import random
from openai import OpenAI


# 导入日志记录模块，用于记录程序运行时的信息
# 导入时间模块，用于处理时间相关操作，如等待
# 从 utils.function_util 模块导入计时装饰器
# 导入随机数模块，用于生成随机数
# 从 openai 库导入 OpenAI 类，用于与 OpenAI 服务进行交互
# 定义一个大语言模型类，封装与大语言模型交互的相关功能
class LargeLanguageModel:
    # 类的构造函数，初始化类的属性
    def __init__(self, api_url, api_key):
        # 创建 OpenAI 客户端实例，配置 API 密钥和基础 URL
        # self.openai_client = OpenAI(
        #     api_key="",
        #     base_url=""
        # )
        self.openai_client = OpenAI(
            api_key=api_key,
            base_url=api_url,
            timeout=120,  # 120s 超时，防止网络 hang 导致进程永久卡住
        )
        # 设置请求失败时的重试次数
        self.retries = 3

    # 使用计时装饰器，记录该方法的执行时间
    def context_chat_completions(self, contexts, model, temperature, top_p, context_number):
        # 进行多次重试，直到达到最大重试次数
        for i in range(self.retries):
            try:
                # 调用 OpenAI 客户端的聊天完成接口，创建聊天完成请求
                messages = [
                    {"role": "system", "content": "You are a helpful assistant."}
                ]
                if len(contexts) < context_number:
                    target_contexts = contexts
                else:
                    target_contexts = contexts[len(contexts) - context_number:len(contexts)]
                messages.extend(target_contexts)
                response = self.openai_client.chat.completions.create(
                    model=model,
                    # 设置聊天消息，包括系统消息和用户消息
                    messages=messages,
                    # 设置温度参数，控制输出的随机性
                    temperature=temperature,
                    # 设置核采样参数，控制输出的多样性
                    top_p=top_p
                )
                # 获取响应中第一条选择的消息内容
                message_content = response.choices[0].message.content
                # 返回消息内容
                return message_content
            except Exception as err:
                # 若请求失败，记录错误信息
                logger.error(f"与模型'{model}' 交互时发生错误: {err}\n{traceback.format_exc()}")
                # 调用退避方法，等待一段时间后重试
                self.backoff()

    def chat_completions(self, prompt, model, temperature, top_p):
        # 进行多次重试，直到达到最大重试次数
        for i in range(self.retries):
            try:
                # 调用 OpenAI 客户端的聊天完成接口，创建聊天完成请求
                response = self.openai_client.chat.completions.create(
                    model=model,
                    # 设置聊天消息，包括系统消息和用户消息
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": prompt},
                    ],
                    # 设置温度参数，控制输出的随机性
                    temperature=temperature,
                    # 设置核采样参数，控制输出的多样性
                    top_p=top_p
                )
                # 获取响应中第一条选择的消息内容，返回消息内容
                return response.choices[0].message.content
            except Exception as err:
                # 若请求失败，记录错误信息
                logger.error(f"与模型'{model}' 交互时发生错误: {err}")
                # 如果是最后一次重试，抛出异常
                if i == self.retries - 1:
                    raise
                # 调用退避方法，等待一段时间后重试
                self.backoff()

    # 定义退避方法，用于在请求失败时等待一段时间
    def backoff(self, wait=None):
        if wait is None:
            # 若未指定等待时间，随机等待 1 到 20 秒
            time.sleep(random.randint(1, 20))
        else:
            # 若指定了等待时间，按指定时间等待
            time.sleep(wait)
