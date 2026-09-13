from customerMilvus_wrapper.customer_milvus import CustomerMilvus

if __name__ == '__main__':
    # 初始化 CustomerMilvus 实例，需根据实际情况修改 URI、模型路径和数据库名
    uri = "http://localhost:19530"
    db_name = "test_db_v1"
    milvus = CustomerMilvus(uri, db_name)



    # 定义集合名称
    collection_name = "test_collection"
    milvus.drop_collection(collection_name)

    # 创建集合
    if not milvus.has_collection(collection_name):
        milvus.create_collection(collection_name)
        print(f"集合 {collection_name} 创建成功")
    else:
        print(f"集合 {collection_name} 已存在")

    milvus.upload_file(collection_name,'./apis/dataset_apis.json')

        # 执行查询
    query = "根据ID查询订单信息"
    topk = 2
    result = milvus.get_docs(collection_name, query, topk)
    print(f"查询 '{query}' 的结果: {result}")



    if milvus.has_collection(collection_name):
        milvus.drop_collection(collection_name)
        print(f"集合 {collection_name} 已删除")