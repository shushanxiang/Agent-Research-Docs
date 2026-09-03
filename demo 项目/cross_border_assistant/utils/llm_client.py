from dashscope import Generation, MultiModalConversation
import dashscope
from config import DASHSCOPE_API_KEY, LLM_MODEL_NAME, VL_MODEL_NAME
import json

dashscope.api_key = DASHSCOPE_API_KEY

def call_llm(prompt: str, system_prompt: str = None, max_retries: int = 2, temperature: float = 0.7) -> str:
    """调用文本生成（同步）。temperature 默认 0.7；分类/意图识别等任务建议传低值(0~0.2)提高确定性"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    for attempt in range(max_retries + 1):
        try:
            response = Generation.call(
                model=LLM_MODEL_NAME,
                messages=messages,
                result_format='message',
                temperature=temperature
            )
            if response.status_code == 200:
                return response.output.choices[0].message.content
            else:
                raise Exception(f"API Error: {response.code} - {response.message}")
        except Exception as e:
            if attempt == max_retries:
                return f"LLM调用失败: {str(e)}"
            continue

def call_vl(image_url: str, prompt: str) -> str:
    """调用通义千问VL识别图片"""
    messages = [
        {
            "role": "user",
            "content": [
                {"image": image_url},
                {"text": prompt}
            ]
        }
    ]
    response = MultiModalConversation.call(
        model=VL_MODEL_NAME,
        messages=messages
    )
    if response.status_code == 200:
        return response.output.choices[0].message.content[0]["text"]
    else:
        raise Exception(f"VL Error: {response.message}")