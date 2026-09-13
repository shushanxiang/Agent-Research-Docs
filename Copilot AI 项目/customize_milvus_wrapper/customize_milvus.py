import json
from typing import List

import yaml
from pymilvus import db, MilvusClient, DataType, connections, Collection
from tqdm import tqdm

from entity import Parameter, Tool
from models import RemoteEmbeddingModel
from pymilvus.client.types import LoadState
from urllib.parse import urlparse


class CustomizeMilvus:

    def __init__(self, uri, db_name):
        """
        CustomerMilvus 类的初始化方法，用于初始化 Milvus 数据库连接。

        参数:
            uri (str): Milvus 数据库的连接 URI。
            db_name (str): Milvus 数据库的名称。
        """
        url_parsed = urlparse(uri)
        conn = connections.connect(host=url_parsed.hostname, port=url_parsed.port)
        databases = db.list_database()
        self.embeddingModel = RemoteEmbeddingModel()
        if db_name not in databases:
            db.create_database(db_name)
        self.client = MilvusClient(
            uri=uri,
            db_name=db_name
        )



    def list_collections(self, ):
        """
        列出所有集合。
        返回:
            list: 所有集合的名称列表。
        """
        return self.client.list_collections()



    def has_collection(self, collection_name):
        """
        检查集合是否存在。
        参数:
            collection_name (str): 集合的名称。
        返回:
            bool: 如果集合存在则返回 True，否则返回 False。
        """
        return collection_name in self.list_collections()


    def load_collection_into_memory(self, collection_name):
        """
        加载集合到内存。
        参数:
            collection_name (str): 集合的名称。
        返回:
            None
        """
        if self.client.get_load_state(collection_name)['state'] == LoadState.NotLoad:
            self.client.load_collection(collection_name)


    def create_collection(self, collection_name):
        """
        创建集合。
        参数:
            collection_name (str): 集合的名称。
        返回:
            None
        """
        schema = MilvusClient.create_schema(
            enable_dynamic_field=False
        )
        schema.add_field(field_name="tool_id", datatype=DataType.INT64, is_primary=True)
        schema.add_field(field_name="embedding", datatype=DataType.FLOAT_VECTOR, dim=1024)
        schema.add_field(field_name="operation_summary", datatype=DataType.VARCHAR, max_length=4096, description="工具名称")

        index_params = MilvusClient.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            metric_type="COSINE",
            index_type="AUTOINDEX"
        )
        self.client.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=index_params
        )


    def insert_embeddings(self, collection_name, embeddings, datas):
        """
        插入嵌入数据。
        参数:
            collection_name (str): 集合的名称。
            embeddings (list): 嵌入数据列表。
            datas (list): 原始数据列表。
        返回:
            None
        """
        self.load_collection_into_memory(collection_name)
        batch_datas = []
        for data, embedding in tqdm(zip(datas, embeddings)):
            data['embedding'] = embedding
            batch_datas.append(data)
            if len(batch_datas) == 10:
                self.client.insert(collection_name=collection_name, data=batch_datas)
                batch_datas = []
        if batch_datas:
            self.client.insert(collection_name=collection_name, data=batch_datas)
            batch_datas = []

    def drop_collection(self, collection_name):
        self.client.drop_collection(
            collection_name=collection_name
        )



    def insert_tools(self, collection_name, tools: List[Tool]):
        """
        将工具信息列表存入指定的 Milvus 集合中。
        参数:
            collection_name (str): 集合的名称。
            tools (list): 工具对象列表。
        返回:
            None
        """
        if not self.has_collection(collection_name):
            self.create_collection(collection_name)
        embeddings, datas = self.embed_chunked_data(tools)
        self.insert_embeddings(collection_name, embeddings, datas)


    def embed_chunked_data(self, tools: List[Tool]):
        """
        将工具信息列表转为嵌入数据
        参数:
            tools (list): 工具对象列表。
        返回:
            tuple: 包含嵌入数据和原始数据的元组。
        """
        datas = []
        chunk_texts = []
        for tool in tools:
            new_data = {
                "tool_id": tool.tool_id,
                "operation_summary": f"{tool.operationId}: {tool.name_for_human}: {tool.description}",

            }
            datas.append(new_data)
            chunk_texts.append(new_data["operation_summary"])
        embeddings = self.embeddingModel.get_batch_embeddings(chunk_texts)
        return embeddings, datas


    def get_docs(self, collection_name, query, topk=5, similarity_threshold=None):
        """
        用于根据查询语句从指定的 Milvus 集合中获取相关文档的 ID。
        该函数接收一个查询语句、集合名称和返回文档数量，通过与 Milvus 数据库交互获取相关文档 ID。
        代码流程逻辑如下：
            1. 确保目标集合已加载到内存中，便于后续搜索操作。
            2. 对输入的查询语句进行嵌入处理，将其转换为向量表示。
            3. 使用转换后的查询向量在 Milvus 集合中进行搜索，设置搜索参数、返回结果数量等。
            4. 解析搜索结果，提取每个匹配文档的工具 ID（COSINE 距离转为相似度，低于阈值则丢弃）。
        参数:
            collection_name (str): 集合的名称。
            query (str): 查询语句。
            topk (int): 返回的文档数量。
            similarity_threshold (float, optional): COSINE 相似度最低门槛，低于此值的工具将被过滤。
        返回:
            list: 包含文档 ID 的列表。
        """
        self.load_collection_into_memory(collection_name)
        query_embedding = self.embeddingModel.get_embedding(query)
        search_params = {
            "metric_type": "COSINE",
            "params": {"level": 1},
        }
        if similarity_threshold is not None:
            search_params["params"]["radius"] = similarity_threshold
        response = self.client.search(
            collection_name=collection_name,
            data=[query_embedding],
            search_params=search_params,
            limit=topk,
            output_fields=["tool_id", "operation_summary"],
            consistency_level="Bounded",
        )
        docs = []
        for res in response:
            for result in res:
                chunk = result["entity"]
                docs.append(int(chunk["tool_id"]))
        return docs

    def delete_tools(self, tools: List[Tool]):
        ids = []
        for tool in tools:
            ids.append(tool.tool_id)
        self.client.delete(
            collection_name="tools",
            ids=ids
        )
    def get_all_entity(self,ids):
        entities = self.client.get(collection_name="tools",ids=ids,output_fields=["tool_id", "operation_summary"])
        return entities