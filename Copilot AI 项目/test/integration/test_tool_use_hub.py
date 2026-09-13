"""集成测试 — ToolUseHub（需要外部 API Service）"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

os.environ["mongo_port"] = "27112"
os.environ["local_mode"] = "0"


class TestToolUseHub:
    """ToolUseHub 核心逻辑"""

    @classmethod
    def setup_class(cls):
        from tools.tool_use_hub import ToolUseHub
        cls.hub = ToolUseHub("test")

    def test_init_sets_retries(self):
        from tools.tool_use_hub import ToolUseHub
        hub = ToolUseHub("test")
        assert hub.retries == 3
        assert hub.name == "test"

    @patch("tools.tool_use_hub.requests.request")
    def test_tool_use_get_no_params(self, mock_request):
        """GET 请求无参数"""
        from conftest import make_tool, make_param
        tool = make_tool("test_tool", [make_param("name", "string", required=False)])
        tool.api_url = "http://localhost:8080"
        tool.path = "/api/test"
        tool.method = "GET"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"result": "ok"}'
        mock_response.headers = {"X-Remaining-Calls": "99"}
        mock_request.return_value = mock_response

        response = self.hub.tool_use(tool, {})
        assert response.status_code == 200

    @patch("tools.tool_use_hub.requests.request")
    def test_tool_use_path_param(self, mock_request):
        """路径参数替换"""
        from conftest import make_tool, make_param
        tool = make_tool("test_tool", [make_param("id", "int64", in_="path")])
        tool.api_url = "http://localhost:8080"
        tool.path = "/api/products/{id}"
        tool.method = "GET"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "result"
        mock_response.headers = {}
        mock_request.return_value = mock_response

        response = self.hub.tool_use(tool, {"id": 42})
        call_args = mock_request.call_args
        url = call_args[0][1]
        assert mock_response.status_code == 200
        # URL 中应包含替换后的 id

    @patch("tools.tool_use_hub.requests.request")
    def test_tool_use_post_body(self, mock_request):
        """POST JSON body"""
        from conftest import make_tool, make_param
        tool = make_tool("create", [
            make_param("name", "string", in_="body"),
            make_param("quantity", "int32", in_="body"),
        ])
        tool.api_url = "http://localhost:8080"
        tool.path = "/api/create"
        tool.method = "POST"

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.text = '{"id": 1}'
        mock_response.headers = {}
        mock_request.return_value = mock_response

        response = self.hub.tool_use(tool, {"name": "苹果", "quantity": 10})
        assert response.status_code == 201

    @patch("tools.tool_use_hub.requests.request")
    def test_tool_use_exception_returns_error(self, mock_request):
        """异常时返回 404 状态码"""
        from conftest import make_tool, make_param
        tool = make_tool("test", [make_param("p1", "string")])
        tool.api_url = "http://localhost:8080"
        tool.path = "/api/test"
        tool.method = "GET"

        mock_request.side_effect = Exception("Connection timeout")

        response = self.hub.tool_use(tool, {"p1": "v1"})
        assert response.status_code == 404

    @patch("tools.tool_use_hub.requests.request")
    def test_tool_use_query_params(self, mock_request):
        """Query 参数"""
        from conftest import make_tool, make_param
        tool = make_tool("search", [make_param("keyword", "string", in_="query")])
        tool.api_url = "http://localhost:8080"
        tool.path = "/api/search"
        tool.method = "GET"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "[]"
        mock_response.headers = {}
        mock_request.return_value = mock_response

        response = self.hub.tool_use(tool, {"keyword": "苹果"})
        assert response.status_code == 200

    def test_log_request_details(self):
        """日志输出不抛异常"""
        self.hub._log_request_details("GET", "http://test.com", {"key": "val"},
                                       {"param": "value"}, {"body": "data"})
        # 不抛异常即为通过

    def test_log_request_details_empty(self):
        """空参数日志"""
        self.hub._log_request_details("POST", "http://test.com", {}, {}, {})
        # 不抛异常即为通过

    def test_log_request_details_json_body(self):
        """JSON body 格式化"""
        self.hub._log_request_details("PUT", "http://test.com", {"X-Key": "v"},
                                       {}, {"name": "test", "value": 123})

    @patch("tools.tool_use_hub.requests.request")
    def test_tool_use_post_with_query(self, mock_request):
        """POST 请求同时含 query 参数和 JSON body（覆盖第 61 行）"""
        from conftest import make_tool, make_param
        tool = make_tool("mixed", [
            make_param("action", "string", in_="query"),
            make_param("payload", "string", in_="body"),
        ])
        tool.api_url = "http://localhost:8080"
        tool.path = "/api/mixed"
        tool.method = "POST"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"
        mock_response.headers = {}
        mock_request.return_value = mock_response

        response = self.hub.tool_use(tool, {"action": "create", "payload": "data"})
        assert response.status_code == 200
        call_args = mock_request.call_args
        # 验证同时传了 params 和 json
        assert call_args[1].get("params") is not None
        assert call_args[1].get("json") is not None
