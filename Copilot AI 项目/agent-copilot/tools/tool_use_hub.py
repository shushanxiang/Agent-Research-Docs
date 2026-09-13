from requests import Response

from entity import Tool
import requests
from utils import logger, RESPONSE_STATUS_CODE_ERROR
import traceback
from tools.tool_manager import ToolManager
from utils import sim_api_key
import json


class ToolUseHub:
    def __init__(self, name):
        self.name = name
        self.retries = 3

    def tool_use(self, tool: Tool, requestBody: dict):
        """
        工具调用方法。该方法根据提供的工具对象和请求参数，调用工具的 API 接口。
        如果工具对象的 API 接口为空，则返回 None。
        参数:
            tool (Tool): 工具对象，包含工具的 API 接口、方法、路径等信息。
            requestBody (dict): 请求参数，以字典形式表示。
        返回:
            requests.Response: 工具 API 接口的响应对象。
            """
        response= Response()
        response.status_code = RESPONSE_STATUS_CODE_ERROR

        try:
            url = f"{tool.api_url}{tool.path}"
            logger.info(f"准备调用工具[{url}：{requestBody}]....")
            param_request = {}
            for param in tool.request_body:
                if param.name in requestBody:
                    if param.in_ == "path":
                        url = url.replace("{"+param.name+"}",str(requestBody[param.name]))
                        requestBody.pop(param.name)
                    elif param.in_ == "query":
                        param_request[param.name] = requestBody[param.name]
                        requestBody.pop(param.name)

            # 创建包含 API 密钥的请求头
            headers = {"X-API-Key": sim_api_key}
            # 对于需要 JSON 请求体的请求，添加 content-type 头部
            if len(requestBody.keys()) > 0:
                headers["content-type"] = "application/json"

            # 打印请求的详细信息
            self._log_request_details(tool.method.upper(), url, headers, param_request, requestBody)

            if len(requestBody.keys()) == 0:
                if len(param_request.keys()) == 0:
                    response = requests.request(tool.method.upper(), url, headers=headers)
                else:
                    response = requests.request(tool.method.upper(), url,params=param_request, headers=headers)
            else:
                if len(param_request.keys()) == 0:
                    response = requests.request(tool.method.upper(), url, json=requestBody, headers=headers)
                else:
                    response = requests.request(tool.method.upper(), url, params=param_request,json=requestBody, headers=headers)

            # 获取并记录剩余调用次数
            remaining_calls = response.headers.get('X-Remaining-Calls', 'N/A')
            logger.info(f"API 调用成功，剩余调用次数: {remaining_calls}")
        except Exception as e:
            logger.error(f"调用工具[{url}：{requestBody}]失败: {e}\n{traceback.format_exc()}")
            return response

        return response

    def _log_request_details(self, method, url, headers, params, body):
        """
        打印请求的详细信息
        """
        # 收集所有日志信息到一个字符串列表中
        log_lines = [
            "======= 请求详情 =======",
            f"请求方法: {method}",
            f"请求URL: {url}",
            "请求头:"
        ]
        
        # 添加请求头信息
        for key, value in headers.items():
            log_lines.append(f"  {key}: {value}")
        
        # 添加查询参数
        log_lines.append("查询参数:")
        if params:
            for key, value in params.items():
                log_lines.append(f"  {key}: {value}")
        else:
            log_lines.append("  无")
        
        # 添加请求体
        log_lines.append("请求体:")
        if body:
            try:
                # 如果是字典，格式化输出
                formatted_body = json.dumps(body, ensure_ascii=False, indent=2)
                log_lines.append(formatted_body)
            except Exception:
                # 如果不是JSON，直接输出
                log_lines.append(str(body))
        else:
            log_lines.append("  无")
            
        log_lines.append("====================")
        
        # 一次性记录所有日志信息，避免多次调用logger
        logger.info("\n".join(log_lines))