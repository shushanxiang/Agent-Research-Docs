import json
import time

import pandas as pd

from param_extraction.param_extraction_hub import ParamExtractionHub
from tools import ToolManager


# 里程碑3

def construct_param_dataset(filepath, target_filepath):
    df = pd.read_csv(filepath)

    results = []

    for index, row in df.iterrows():
        # 获取当前行的索引
        print(f'索引: {index}')
        # 获取当前行的列值
        parameters = {}
        parameter_lines = row["Parameter"].split("\n")
        for line in parameter_lines:
            key = line.split(":")[0].strip()
            value = line.split(":")[1].strip()
            parameters[key] = value

        results.append({
            "Query": row["Query"],
            "API": row["API"],
            "Parameter": parameters
        })
    with open(target_filepath, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

def cal_correct_rate(test_result):
    correct_num = 0
    correct_param_num = 0
    total_param_num = 0
    with open(test_result,encoding='utf-8') as f:
        datas = json.load(f)
        for data in datas:
            ground_truth_param = data["raw_data"]["Parameter"]
            test_param = data["test_result"]
            total_param_num += len(ground_truth_param.keys())
            flag = True
            for k,v in ground_truth_param.items():
                if k in test_param and test_param[k] == v:
                    correct_param_num += 1
                    continue
                else:
                    flag = False
            if flag:
                correct_num += 1
    print(correct_num/len(datas))
    print(correct_param_num/total_param_num)

def test_param_extraction(dataset, test_result):
    toolManager = ToolManager('localhost', "tools", 27017)
    toolManager.delete_all_tools()
    toolManager.upload_file("./apis/dataset_retail_field.yaml")
    time.sleep(5)
    paramExtractionHub = ParamExtractionHub(model="deepseek-v3", temperature=0.67, top_p=0.95)
    results = []
    with open(dataset, encoding='utf-8') as f:
        datas = json.load(f)
        for data in datas:
            tool = toolManager.get_tools_by_operationIds([data["API"]])[0]
            final_parameters,_ = paramExtractionHub.extraction_params(data["Query"], tool)
            results.append({
                "raw_data": data,
                "test_result": final_parameters
            })
            print(final_parameters)
            print("==================")
    with open(test_result, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    # toolManager.delete_all_tools()


if __name__ == "__main__":
    # construct_param_dataset("testData/test_data_retail.csv","testData/param_extraction_dataset.json")
    test_param_extraction(dataset="../testData/param_extraction_dataset.json",
                          test_result="../testData/param_extraction_result.json")
    # cal_correct_rate(test_result="testData/param_extraction_result.json")
