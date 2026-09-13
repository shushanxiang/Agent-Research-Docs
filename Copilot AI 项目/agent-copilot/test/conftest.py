"""pytest 全局 fixtures"""

import json
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# 确保项目根目录在 sys.path 中
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# pytest 标记注册
pytest.register_assert_rewrite("test.unit", "test.integration")

# ===== Mock 工具数据 =====

@pytest.fixture
def sample_tools():
    """加载模拟工具集"""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "mock_tools.json")
    if os.path.exists(fixture_path):
        with open(fixture_path, "r", encoding="utf-8") as f:
            return json.load(f)

    return [
        {
            "tool_id": 1,
            "operationId": "getByProductName",
            "name_for_human": "按名称查询产品",
            "name_for_model": "tool1",
            "description": "根据产品名称模糊查询产品信息",
            "api_url": "http://localhost:8080",
            "path": "/api/products/name",
            "method": "GET",
            "request_body": [
                {"name": "productName", "type": "string", "description": "产品名称关键词",
                 "required": True, "enum": [], "format": "", "in_": "query"}
            ],
            "isValidate": False,
        },
        {
            "tool_id": 2, "operationId": "getByProductId",
            "name_for_human": "按ID查询产品", "name_for_model": "tool2",
            "description": "根据产品ID精确查询产品详细信息",
            "api_url": "http://localhost:8080", "path": "/api/products/{id}", "method": "GET",
            "request_body": [
                {"name": "productId", "type": "int64", "description": "产品ID",
                 "required": True, "enum": [], "format": "", "in_": "path"}
            ],
            "isValidate": False,
        },
        {
            "tool_id": 3, "operationId": "createOrder",
            "name_for_human": "创建订单", "name_for_model": "tool3",
            "description": "创建新的采购/销售订单",
            "api_url": "http://localhost:8080", "path": "/api/orders", "method": "POST",
            "request_body": [
                {"name": "productId", "type": "int64", "description": "产品ID", "required": True, "enum": [], "format": "", "in_": "body"},
                {"name": "quantity", "type": "int32", "description": "数量", "required": True, "enum": [], "format": "", "in_": "body"},
                {"name": "supplierId", "type": "int64", "description": "供应商ID", "required": True, "enum": [], "format": "", "in_": "body"},
                {"name": "orderRegion", "type": "string", "description": "配送区域", "required": True, "enum": [], "format": "", "in_": "body"},
            ],
            "isValidate": True,
        },
        {
            "tool_id": 4, "operationId": "getOrdersByDateRange",
            "name_for_human": "按日期范围查询订单", "name_for_model": "tool4",
            "description": "根据起止日期查询订单列表",
            "api_url": "http://localhost:8080", "path": "/api/orders/range", "method": "GET",
            "request_body": [
                {"name": "startDate", "type": "date-time", "description": "起始日期", "required": True, "enum": [], "format": "date-time", "in_": "query"},
                {"name": "endDate", "type": "date-time", "description": "结束日期", "required": True, "enum": [], "format": "date-time", "in_": "query"},
            ],
            "isValidate": False,
        },
        {
            "tool_id": 5, "operationId": "queryOrders",
            "name_for_human": "查询订单", "name_for_model": "tool5",
            "description": "查询订单信息",
            "api_url": "http://localhost:8080", "path": "/api/orders", "method": "GET",
            "request_body": [
                {"name": "status", "type": "string", "description": "订单状态", "required": False,
                 "enum": ["已完成", "待发货", "已取消"], "format": "enum", "in_": "query"},
            ],
            "isValidate": False,
        },
    ]


@pytest.fixture
def tool_entities(sample_tools):
    """将模拟工具数据转为 Tool 实体列表"""
    from entity.tool_entity import Tool, Parameter
    entities = []
    for td in sample_tools:
        params = []
        for pd in td["request_body"]:
            params.append(Parameter(
                name=pd["name"], type=pd["type"], description=pd["description"],
                required=pd["required"], enum=pd.get("enum", []),
                format=pd.get("format", ""), in_=pd["in_"],
            ))
        tool = Tool()
        tool.tool_id = td["tool_id"]
        tool.operationId = td["operationId"]
        tool.name_for_human = td["name_for_human"]
        tool.name_for_model = td["name_for_model"]
        tool.description = td["description"]
        tool.api_url = td["api_url"]
        tool.path = td["path"]
        tool.method = td["method"]
        tool.request_body = params
        tool.isValidate = td.get("isValidate", False)
        entities.append(tool)
    return entities


# ===== Mock LLM =====

@pytest.fixture
def mock_llm():
    """模拟 LLM，返回预定义响应"""
    with patch("models.llm.LargeLanguageModel") as mock:
        instance = mock.return_value
        instance.chat_completions.return_value = "mock LLM response"
        yield instance


@pytest.fixture
def mock_llm_with_responses():
    """模拟 LLM，根据 prompt 关键词返回不同响应"""
    responses = {}
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "mock_llm_responses.json")
    if os.path.exists(fixture_path):
        with open(fixture_path, "r", encoding="utf-8") as f:
            responses = json.load(f)
    with patch("models.llm.LargeLanguageModel") as mock:
        instance = mock.return_value
        def side_effect(prompt, model, temperature, top_p):
            for keyword, response in responses.items():
                if keyword in prompt:
                    return response
            return "{}"
        instance.chat_completions.side_effect = side_effect
        yield instance


# ===== 帮助函数 =====

def make_param(name, type_="int32", required=True, enum=None, format_="", in_="query"):
    """快速创建 Parameter 实体"""
    from entity.tool_entity import Parameter
    p = Parameter()
    p.name = name
    p.type = type_
    p.description = f"{name}参数"
    p.required = required
    p.enum = enum or []
    p.format = format_
    p.in_ = in_
    return p


def make_tool(name="test_tool", params=None, is_validate=False):
    """快速创建 Tool 实体"""
    from entity.tool_entity import Tool
    t = Tool()
    t.tool_id = 1
    t.operationId = name
    t.name_for_human = name
    t.name_for_model = name
    t.description = f"{name}的描述"
    t.request_body = params or []
    t.isValidate = is_validate
    return t


class MockTask:
    """模拟 Task 实体，用于循环检测测试"""
    def __init__(self, nodes=None, task_id="test-001"):
        self.task_id = task_id
        self.nodes = nodes or []
        self.curr_tool_id = -1
        self.curr_tool_param = {}
        self.task_type = 2
        self.changed_query = "test query"
        self.raw_query = "test raw query"
        self.edges = []
