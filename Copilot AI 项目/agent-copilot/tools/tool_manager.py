import json
import time
from typing import List

from mongoengine import *
import threading
from cachetools import TTLCache
import yaml
from utils import logger, model_api_key

from customize_milvus_wrapper import CustomizeMilvus
from entity import Parameter, Tool

# 本地重排序模型导入
# from models.reranker_model import get_reranker_instance
# 导入通义千问重排序模型
from models.qwen_reranker_model import get_qwen_reranker_instance
import os
from mongoengine import connect, disconnect, get_connection
from dotenv import load_dotenv
load_dotenv()


class ToolManager:
    def __init__(self, mongo_host, mongo_db, mongo_port, milvus_uri, milvus_db_name):
        try:
            # 检查是否已有连接
            existing_connection = get_connection()
            if existing_connection:
                disconnect()  # 断开现有连接
        except Exception as e:
            logger.warning(f"检查ToolManager的已有MongoDB连接: {e}，已重建连接 。")
        self.mongoClient = connect(mongo_db, host=mongo_host, port=mongo_port)
        self.db_name = mongo_db  # 保存数据库名称
        self.cache_lock = threading.Lock()
        self.tool_cache = TTLCache(maxsize=100, ttl=3600)
        self.milvus = CustomizeMilvus(milvus_uri, milvus_db_name)
        if model_api_key:
            self.reranker = get_qwen_reranker_instance(model_api_key)
        else:
            raise ValueError("请设置model_api_key环境变量")

    def delete_all_tools(self):
        """
        工具删除方法。该方法根据提供的工具 ID，从数据库中删除对应的工具。
        如果工具 ID 为空，则返回 None。
        参数:
            tool_id (int): 工具 ID，用于唯一标识要删除的工具。
        返回:
            None
        """
        Tool.objects.delete()
        self.milvus.drop_collection(collection_name="tools")
        self.clear_cache()

    def get_raw_all_tools(self):
        return Tool.objects.all()

    def get_all_tools(self):
        tools = Tool.objects.all()
        results = []
        index = 1
        for tool in tools:
            arguments = []
            for chat_parameter in tool.request_body:
                arguments.append({
                    "name": chat_parameter.name,
                    "description": chat_parameter.description,
                    "schema": {
                        "type": chat_parameter.type,
                        "format": chat_parameter.format,
                        "enum": chat_parameter.enum,
                    }
                })
            requestBody = json.dumps(arguments, ensure_ascii=False)
            results.append({
                "key": tool.tool_id,
                "index": index,
                "name": tool.name_for_human,
                "description": tool.description,
                "params": requestBody,
                "method": tool.method
            })
            index += 1
        return results

    def delete_tools(self,tool_ids):
        tools = self.get_tools_by_ids(tool_ids)
        for tool in tools:
            Tool.objects(tool_id=tool.tool_id).delete()
        self.milvus.delete_tools(tools)
        self.clear_cache()

    # def max_id(self):
    #     with self.cache_lock:
    #         tools = Tool.objects().all()
    #         max_target_id = -1
    #         for tool in tools:
    #             if tool.tool_id > max_target_id:
    #                 max_target_id = tool.tool_id
    #         if max_target_id == -1:
    #             return 0
    #         else:
    #             return max_target_id

    def get_next_tool_id(self):
        db = self.mongoClient[self.db_name]
        # 使用findAndModify原子操作
        counter = db.mongoClient.counters.find_one_and_update(
            {"_id": "tool_id"},
            {"$inc": {"sequence_value": 1}},
            upsert=True,
            return_document=True
        )
        return counter["sequence_value"]

    def insert_tools(self, tools: List[Tool]):
        new_tools = []
        for tool in tools:
            tool.tool_id = self.get_next_tool_id()
            tool.save()
            new_tools.append(tool)
        self.milvus.insert_tools("tools", new_tools)

        return tools

    def clear_cache(self):
        """
        工具缓存清除方法。该方法清除工具缓存中的所有工具。
        """
        with self.cache_lock:
            tool_ids = self.tool_cache.keys()
            for tool_id in tool_ids:
                self.tool_cache.pop(tool_id, None)


    def get_tools_by_ids_from_mongo(self, tool_ids: List[int]):
        """
        工具 ID 列表查询方法。该方法根据提供的工具 ID 列表，从数据库中查询对应的工具对象。
        如果工具 ID 列表为空，则返回空列表。
        参数:
            tool_ids (List[int]): 工具 ID 列表，用于唯一标识要查询的工具。
        返回:
            List[Tool]: 工具对象列表。
        """
        tools = []
        for tool_id in tool_ids:
            try:
                tool = Tool.objects.get(tool_id=tool_id)
                tools.append(tool)
            except:
                logger.info(f"User with id {tool_id} does not exist.")
                continue
        return tools



    def get_tools_by_ids(self, tool_ids: List[int]) -> List[Tool]:
        """
        工具 ID 列表查询方法。该方法根据提供的工具 ID 列表，从数据库中查询对应的工具对象。
        如果工具 ID 列表为空，则返回空列表。
        参数:
            tool_ids (List[int]): 工具 ID 列表，用于唯一标识要查询的工具。
        返回:
            List[Tool]: 工具对象列表。
        """
        if len(tool_ids) == 0:
            return []
        with self.cache_lock:
            cached_tools = [self.tool_cache.get(pid) for pid in tool_ids]

        #进行缓存更新，将缓存中不存在的工具添加到缓存中
        missing_tool_ids = [tool_id for tool_id, tool in zip(tool_ids, cached_tools) if tool is None]
        cached_tools = [tool for tool in cached_tools if tool is not None]
        if missing_tool_ids:
            data = self.get_tools_by_ids_from_mongo(missing_tool_ids)
            for tool in data:
                with self.cache_lock:
                    self.tool_cache[tool.tool_id] = tool

                cached_tools.append(tool)
        return cached_tools



    def get_tools_by_operationIds(self, operationIds) -> List[Tool]:
        """
        工具 operationId 列表查询方法。该方法根据提供的工具 operationId 列表，从数据库中查询对应的工具对象。
        如果工具 operationId 列表为空，则返回空列表。
        参数:
            operationIds (List[int]): 工具 operationId 列表，用于唯一标识要查询的工具。
        返回:
            List[Tool]: 工具对象列表。
        """
        tools = []
        for operationId in operationIds:
            try:
                tool = Tool.objects.get(operationId=operationId)
                tools.append(tool)
            except:
                logger.info(f"User with id {operationId} does not exist.")
                continue
        return tools



    def upload_file(self, filename):
        """
        工具文件上传方法。该方法根据提供的工具文件，将工具上传到数据库中。
        如果工具文件为空，则返回 None。
        参数:
            filename (str): 工具文件路径，用于唯一标识要上传的工具。
        返回:
            None
        """
        # 读取 JSON 文件
        with open(filename, 'r', encoding='utf-8') as file:
            data = json.load(file)
            schemas = data["components"]["schemas"]

        tools = []
        url = data["servers"][0]["url"]
        index = 0
        for path in data["paths"]:
            for method in data["paths"][path]:
                index += 1
                api_information = data["paths"][path][method]
                operationIds = path.split('/')
                for i in range(len(operationIds)):
                    if "{" in operationIds[len(operationIds) - 1 - i] and "}" in operationIds[
                        len(operationIds) - 1 - i]:
                        continue
                    else:
                        operationId = operationIds[len(operationIds) - 1 - i]
                        break
                name_for_human = api_information["summary"]
                name_for_model = "tool" + str(index)

                description = api_information["description"]
                params = []
                if "parameters" in api_information:
                    requestParams = api_information["parameters"]
                    for param in requestParams:
                        param_name = param["name"]
                        # logging.info(requestParams[param])
                        param_description = param["description"]
                        in_ = param["in"]
                        # logging.info(requestParams[param])
                        if param["schema"]["type"] == "string":
                            paramType = "string"
                        elif param["schema"]["type"] == "array":
                            paramType = "array"
                        else:
                            paramType = param["schema"]["format"]
                        enum = []
                        if "enum" in param["schema"]:
                            enum = param["schema"]["enum"]

                        required = True
                        parameter = Parameter(
                            name=param_name,
                            type=paramType,
                            description=param_description,
                            enum=enum,
                            required=required,
                            in_=in_

                        )
                        params.append(parameter)

                if "requestBody" in api_information:
                    requestBody = \
                        api_information["requestBody"]["content"]["application/json"]["schema"]["$ref"].split('/')[-1]
                    requestParams = schemas[requestBody]["properties"]
                    for param in requestParams:
                        param_name = param
                        # logging.info(requestParams[param])
                        param_description = requestParams[param]["description"]
                        # logging.info(requestParams[param])
                        if requestParams[param]["type"] == "string":
                            paramType = "string"
                        elif requestParams[param]["type"] == "array":
                            paramType = "array"
                        else:
                            paramType = requestParams[param]["format"]
                        enum = []
                        if "enum" in requestParams[param]:
                            enum = requestParams[param]["enum"]
                        if "format" in requestParams[param]:
                            format = requestParams[param]["format"]
                        else:
                            format = paramType

                        if len(enum) != 0:
                            format = "enum"

                        required = True
                        parameter = Parameter(
                            name=param_name,
                            type=paramType,
                            description=param_description,
                            enum=enum,
                            required=required,
                            format=format,
                            in_="requestBody"
                        )
                        params.append(parameter)
                else:
                    requestParams = []
                if "查询" in name_for_human or "获取" in name_for_human:
                    isValidate = False
                else:
                    isValidate = True

                tool = Tool(
                    tool_id=index,
                    operationId=operationId,
                    name_for_human=name_for_human,
                    name_for_model=name_for_model,
                    description=description,
                    api_url=url,
                    isValidate=isValidate,
                    path=path,
                    method=method,
                    request_body=params

                )
                tools.append(tool)
        self.insert_tools(tools)
        return tools
    def test_milvus(self,ids):
        return self.milvus.get_all_entity(ids)

    def search_tools_with_rerank(self, query, top_k=20, final_top_n=5):
        """
        使用重排序模型进行工具搜索
        Args:
            query (str): 查询文本
            top_k (int): 向量检索召回数量
            final_top_n (int): 最终返回结果数量
        Returns:
            list: 重排序后的工具列表
        """
        # 1. 向量检索获取候选工具ID
        candidate_tool_ids = self.milvus.get_docs("tools", query, topk=top_k)
        # 2. 从MongoDB获取候选工具详细信息
        candidate_tools = self.get_tools_by_ids(candidate_tool_ids)
        # 3. 准备重排序的文本
        candidates_for_rerank = [f"{tool.name_for_human}: {tool.description}" for tool in candidate_tools]
        # 4. 重排序
        reranked_indices = self.reranker.rerank(query, candidates_for_rerank)
        # 5. 根据重排序结果整理最终工具列表
        final_tools = [candidate_tools[i] for i in reranked_indices]
        
        return final_tools[:final_top_n]
