import json
from typing import List

import numpy as np
import yaml
from pymilvus import db, MilvusClient, DataType, connections
from tqdm import tqdm

from pymilvus.client.types import LoadState
from urllib.parse import urlparse

if __name__ == "__main__":
    uri = "http://localhost:19530"
    db_name = "test_db_v1"
    collection_name = "test_collection_v1"
    url_parsed = urlparse(uri)
    conn = connections.connect(host=url_parsed.hostname, port=url_parsed.port)
    # 查看当前milvus中的数据库
    databases = db.list_database()
    print(databases)
    # 如果db_name 不在数据库中，就创建数据库
    if db_name not in databases:
        db.create_database(db_name)
    # 创建milvus客户端
    client = MilvusClient(
        uri=uri,
        db_name=db_name
    )

    # 创建collection schema
    schema = MilvusClient.create_schema(
        enable_dynamic_field=False
    )
    schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
    schema.add_field(field_name="embedding", datatype=DataType.FLOAT_VECTOR, dim=1024)

    # 创建索引
    index_params = MilvusClient.prepare_index_params()
    index_params.add_index(
        field_name="embedding",
        metric_type="IP",
        index_type="FLAT",
        params={"nlist": 2048}
    )
    # 创建collection
    if collection_name in client.list_collections():
        client.drop_collection(collection_name)

    client.create_collection(
        collection_name=collection_name,
        schema=schema,
        index_params=index_params
    )

    # 随机生成10条数据

    datas = []
    query_array = None
    for i in range(1000):

        vectors_array = np.random.rand(1024)
        if query_array is None:
            query_array = vectors_array
        datas.append({
            "id": i,
            "embedding": vectors_array
        })

    # 如果 collection 未加载在内存中，请先加载内存
    if client.get_load_state(collection_name)['state'] == LoadState.NotLoad:
        client.load_collection(collection_name)

    # 插入这十条数据
    client.insert(collection_name=collection_name, data=datas, batch_size=len(datas))

    # 生成随机的查询向量
    vectors_array = np.random.rand(1024)

    # 从milvus 中进行查询操作

    response = client.search(
        collection_name=collection_name,  # Collection name
        data=[vectors_array.tolist()],
        search_params={
            "metric_type": "IP",
            "params": {"nprobe": 16},  # Search parameters
        },  # Search parameters
        limit=100,  # Max. number of search results to return
        output_fields=["id"],
        # Fields to return in the search results
        consistency_level="Bounded",
    )
    # 对milvus结果进行解析
    docs = []
    print(response)
    for res in response:
        for result in res:
            # print(result)
            chunk = result["entity"]
            docs.append({
                "id": chunk["id"]
            })
    print(docs)
    # client.drop_collection(collection_name)
    # db.drop_database(db_name)
    print(db.list_database())
