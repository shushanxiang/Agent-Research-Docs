import numpy as np
from openai import OpenAI


class RemoteEmbeddingModel:
    """
    初始化 RemoteEmbeddingModel 类的实例。
    此方法会创建一个 OpenAI 客户端实例，用于后续的嵌入向量生成操作。

    Attributes:
        openai_client (OpenAI): OpenAI 客户端实例，用于与 OpenAI API 进行交互。
                                配置了 API 密钥和基础 URL。
    """

    def __init__(self):
        from utils.config import model_api_key, model_base_url
        self.openai_client = OpenAI(
            api_key=model_api_key,
            base_url=model_base_url
        )
        # self.openai_client = OpenAI(
        #     api_key="admin1234",
        #     base_url="http://localhost:7997"
        # )

    # text-embedding-3-large

    """
    根据输入的文本获取对应的嵌入向量。

    此函数会调用 OpenAI 客户端的嵌入向量生成接口，使用指定的模型 `text-embedding-3-large` 来生成文本的嵌入向量。

    参数:
        text (str): 用于生成嵌入向量的输入文本。

    返回:
        list: 生成的文本嵌入向量，以列表形式返回。

    代码流程逻辑:
        1. 调用 OpenAI 客户端的 `embeddings.create` 方法，传入模型名称和输入文本，获取响应。
        2. 从响应结果中提取第一个数据项的嵌入向量。
        3. 返回提取的嵌入向量。
    """

    # text-embedding-3-large
    def get_embedding(self, text):
        response = self.openai_client.embeddings.create(model="text-embedding-v3", input=text)
        embeddings = response.data[0].embedding
        return embeddings

    # text-embedding-3-large

    """
    根据输入的多个文本批量获取对应的嵌入向量。

    此函数会调用 OpenAI 客户端的嵌入向量生成接口，使用指定的模型 `text-embedding-3-large` 来批量生成文本的嵌入向量。

    参数:
        texts (list): 用于生成嵌入向量的输入文本列表，列表中的每个元素为一个字符串。

    返回:
        list: 生成的文本嵌入向量列表，列表中的每个元素为对应输入文本的嵌入向量。

    代码流程逻辑:
        1. 调用 OpenAI 客户端的 `embeddings.create` 方法，传入模型名称和输入文本列表，获取响应。
        2. 从响应结果中提取每个数据项的嵌入向量。
        3. 将提取的嵌入向量添加到结果列表中。
        4. 返回结果列表。
    """

    # def get_batch_embeddings(self, texts):
    #     response = self.openai_client.embeddings.create(model="text-embedding-v3", input=texts)
    #     embeddings = response.data
    #     results = []
    #     for tmp in embeddings:
    #         results.append(tmp.embedding)
    #     return results

    def get_batch_embeddings(self, texts, batch_size=10):
        """
        批量获取文本嵌入向量，支持超过10个文本的处理
        参数:
            texts (list): 输入文本列表
            batch_size (int): 每批处理的文本数量，默认为10
        返回:
            list: 文本嵌入向量列表
        """
        all_embeddings = []

        # 将文本列表分批处理
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            response = self.openai_client.embeddings.create(
                model="text-embedding-v3",
                input=batch_texts
            )
            embeddings = response.data
            for tmp in embeddings:
                all_embeddings.append(tmp.embedding)

        return all_embeddings

    """
    根据输入的查询向量和文本向量列表，计算查询向量与文本向量的余弦相似度。

    此函数会根据输入的查询向量和文本向量列表，使用余弦相似度来计算它们之间的相似程度。余弦相似度是一种常用的相似度度量方法，用于衡量两个向量之间的夹角余弦值。

    参数:
        target_texts (list): 文本向量列表，列表中的每个元素为一个文本向量。
        vectors (list): 文本向量列表，列表中的每个元素为一个文本向量。
        query (list): 查询向量，用于与文本向量进行比较。
        recall_num (int): 返回的相似文本数量，默认为 5。
        threshold (float): 相似度阈值，默认为 0。

    返回:
        list: 相似文本列表，列表中的每个元素为一个文本向量。

    代码流程逻辑:
        1. 将查询向量和文本向量列表转换为 numpy 数组。
        2. 计算查询向量的范数。
        3. 计算文本向量列表的范数。
        4. 计算余弦相似度。
        5. 按相似度降序排序。
        6. 返回相似文本列表。
    """

    def get_similarity(self, target_texts, vectors, query, recall_num: int = 5, threshold: float = 0):
        query = np.array(query)
        vectors = np.array(vectors)

        # 计算余弦相似度
        norm_query = np.linalg.norm(query)
        norm_vectors = np.linalg.norm(vectors, axis=1)
        cosine_similarities = np.dot(vectors, query) / (norm_vectors * norm_query)

        # 按相似度降序排序
        sorted_indices = cosine_similarities.argsort()[::-1]

        result_docs = []
        for i in sorted_indices:
            if cosine_similarities[i] > threshold:
                result_docs.append(target_texts[i])
            if recall_num != -1 and len(result_docs) >= recall_num:
                break

        return result_docs
