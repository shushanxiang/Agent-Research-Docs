from agent.base_agent import *
import os

os.environ['APP_TOKEN'] = 'sk-b5d3c6134a7c473e9db05b894c48b332'
os.environ['LLM_BASE_URL'] = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
os.environ['APP_ID'] = 'd09e1854da1040f3838eb3c4af32ce33'
os.environ['GEMINI_API_KEY'] = 'AIzaSyBcvNfIJa1WKXgYjVHzOlKtYXFp2h0WSfQ'

if __name__ == '__main__':
    agent = Agent()
    response = agent("中国的首都是那里？")