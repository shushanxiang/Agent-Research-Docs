import json
from typing import List
from typing_extensions import deprecated

import yaml
from tqdm import tqdm

from entity import Parameter, Tool
import os
import logging

from models import RemoteEmbeddingModel

@deprecated("此类已被弃用，请使用CustomizeMilvus")
class TextMilvus:

    def __init__(self, uri, model_path, db_name):
        self.prefix_filename = f'{uri}_{model_path}_{db_name}'
        self.filename = ""
        self.embeddingModel = RemoteEmbeddingModel()
        self.dir_path = "D:\\agent-copilot\\customerMilvus_wrapper\\"

    def create_collection(self, collection_name):
        if os.path.exists(self.dir_path+self.prefix_filename + f"_{collection_name}.json"):
            logging.info(f"{collection_name} exists")
        else:
            with open(self.dir_path+self.prefix_filename + f"_{collection_name}.json", 'w') as file:
                json.dump([],file,ensure_ascii=False,indent=4)
                pass

    def insert_embeddings(self, collection_name, embeddings, datas):
        filename = self.prefix_filename + f"_{collection_name}.json"
        with open(self.dir_path+filename, 'r+', encoding='utf-8') as f:
            current_datas = json.load(f)

            for data, embedding in tqdm(zip(datas, embeddings)):
                data['embedding'] = embedding
                current_datas.append(data)
        with open(self.dir_path+filename, 'r+',encoding='utf-8') as f:
            json.dump(current_datas, f, ensure_ascii=False, indent=4)

    def drop_collection(self, collection_name):

        if os.path.exists(self.dir_path+self.prefix_filename + f"_{collection_name}.json"):
            os.remove(self.dir_path+ self.prefix_filename + f"_{collection_name}.json")

    def upload_file(self, filename):
        # 读取 JSON 文件
        with open(filename, 'r', encoding='utf-8') as file:
            data = json.load(file)

            schemas = data["components"]["schemas"]

        tools = []
        url = data["servers"][0]["url"]
        index = 0
        logging.info(url)
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

                        required = True
                        parameter = Parameter(
                            name=param_name,
                            type=paramType,
                            description=param_description,
                            enum=enum,
                            required=required,
                            in_="requestBody"
                        )
                        params.append(parameter)
                else:
                    requestParams = []

                tool = Tool(
                    tool_id=index,
                    operationId=operationId,
                    name_for_human=name_for_human,
                    name_for_model=name_for_model,
                    description=description,
                    api_url=url,
                    path=path,
                    method=method,
                    request_body=params

                )
                tools.append(tool)
        embeddings, datas = self.embed_chunked_data(tools)
        self.insert_embeddings("tools", embeddings, datas)

    def embed_chunked_data(self, tools: List[Tool]):

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

    def get_docs(self, collection_name, query, topk=5):
        filename = self.prefix_filename + f"_{collection_name}.json"
        with open(self.dir_path+filename, encoding='utf-8') as f:
            current_datas = json.load(f)

        target_texts = []
        vectors = []
        for tmp in current_datas:
            target_texts.append(tmp["tool_id"])
            vectors.append(tmp["embedding"])
        query_embedding = self.embeddingModel.get_embedding(query)

        results = self.embeddingModel.get_similarity(target_texts, vectors, query_embedding, topk, 0.0)
        return results
