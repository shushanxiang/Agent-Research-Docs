import json
import time

import pandas as pd

from apis import ApiSelectionHub
from customize_milvus_wrapper import CustomizeMilvus
from tools import ToolManager


# 里程碑3
def construct_api_selection_dataset(filepath, target_filepath):
    df = pd.read_csv(filepath)

    results = []

    for index, row in df.iterrows():
        parameters = {}
        parameter_lines = row["Parameter"].split("\n")
        for line in parameter_lines:
            key = line.split(":")[0].strip()
            value = line.split(":")[1].strip()
            parameters[key] = value

        results.append({
            "Query": row["Query"],
            "API": row["API"],
        })
    with open(target_filepath, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)


def test_api_selection(dataset, test_result):
    toolManager = ToolManager('localhost', "tools", 27017)
    toolManager.delete_all_tools()
    toolManager.upload_file("./apis/dataset_retail_field.yaml")
    time.sleep(5)

    customerMilvus = CustomizeMilvus(uri='http://localhost:19530',
                                    model_path="/root/data/models/BAAI/bge-large-zh-v1___5", db_name='tool')
    customerMilvus.drop_collection("tools")

    if not customerMilvus.has_collection("tools"):
        customerMilvus.create_collection("tools")

    customerMilvus.upload_file("./apis/dataset_retail_field.yaml")
    time.sleep(5)

    apiSelectionHub = ApiSelectionHub(milvus_uri='http://localhost:19530', model_path="/root/data/models/BAAI/bge-large-zh-v1___5", milvus_db_name='tool', host='localhost', mongo_db="tools", mongo_port=27017,
                                      model="deepseek-v3", temperature=0.67, top_p=0.95)

    results = []
    with open(dataset, encoding='utf-8') as f:
        datas = json.load(f)
        for data in datas:
            tool = apiSelectionHub.get_tool_coarse_and_fine(data["Query"], 5)
            if tool is None:
                results.append({
                    "raw_data": data,
                    "test_result": ""
                })
            else:
                results.append({
                    "raw_data": data,
                    "test_result": tool.operationId
                })
                print(data["Query"],tool.operationId)
                print("============")
    with open(test_result, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)


def cal_correct_rate(test_result):
    correct_num = 0
    correct_param_num = 0
    total_param_num = 0
    with open(test_result,encoding='utf-8') as f:
        datas = json.load(f)
        for data in datas:
            if data["raw_data"]["API"] == data["test_result"]:
                correct_num += 1
    print(correct_num/len(datas))
    # print(correct_param_num/total_param_num)

if __name__ == "__main__":
    # construct_api_selection_dataset("testData/test_data_retail.csv", "testData/api_selection_dataset.json")
    # test_api_selection("testData/api_selection_dataset.json","testData/api_selection_result.json")
    cal_correct_rate("../testData/api_selection_result.json")