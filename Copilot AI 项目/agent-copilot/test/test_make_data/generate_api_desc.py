import json
import random
from openai import OpenAI

from entity import Tool

client = OpenAI(
    api_key="",
    base_url=""
)


def post_process(text, api_func):
    needs = text.split("\n")
    polish_needs = []
    for need in needs:
        polish_needs.append({"need": need, "API": api_func})

    return polish_needs


def generate_line(tool: Tool):
    api_func = tool.name_for_human
    api_description = tool.description
    prompt_template = """
你是优秀的数据集生成大师。我将给你一个API描述，包括API名称，API功能，API请求参数。请根据API描述，生成该API可以解决的用自然语言描述的用户请求。

API名称：{api_name}
API功能：{api_description}
API请求参数：
{api_param}

输出格式：请输出50个用自然语言描述的用户请求
1. 
2. 
...
50. 
    
    """

    param_template = "API请求参数名称{index}：{name}\nAPI请求参数描述：{description}\nAPI请求参数类型：{type}\n\n"
    total_param_string = ""
    index = 1
    for param in tool.request_body:
        param_string = param_template.format(index=index, name=param.name, description=param.description,
                                             type=param.type)
        total_param_string += param_string
        index += 1

    prompt = prompt_template.format(api_name=api_func, api_description=api_description, api_param=total_param_string)
    response = client.chat.completions.create(
        model="deepseek-v3",
        # 设置聊天消息，包括系统消息和用户消息
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
    )
    message_content = response.choices[0].message.content

    polish_needs = post_process(message_content, api_func)

    return polish_needs

def generate_false_sentences(train_dataset_file):
    with open(train_dataset_file, 'r', encoding="utf-8") as f:
        datas = json.load(f)
        api_sentences = dict()
        for data in datas:
            if data["API"] not in api_sentences:
                api_sentences[data["API"]]= [data["need"]]
            else:
                x = api_sentences[data["API"]]
                x.append(data["need"])
                api_sentences[data["API"]] = x
        negative_sentence = None
        new_results = []
        for data in datas:
            target_api = data["API"]
            while True:
                apis = api_sentences.keys()
                negative_api = random.choice(list(apis))
                if negative_api != target_api:
                    negative_sentence = random.choice(api_sentences[negative_api])
                    break
            new_results.append({
                "api": data["API"],
                "sentences": data["need"],
                "negative_sentences": negative_sentence
            })
    with open("../testData/new_dataset_train.json", 'w', encoding="utf-8") as f:
        json.dump(new_results, f, ensure_ascii=False, indent=4)





if __name__ == "__main__":
    # toolManager = ToolManager('localhost', "tools", 27017)
    # # toolManager.delete_all_tools()
    # # toolManager.upload_file("./apis/dataset_apis.json")
    #
    # results = []
    #
    # for i in range(22):
    #     tool = toolManager.get_tools_by_ids([i + 1])[0]
    #     # print(tool.tool_id, tool.name_for_human)
    #     polish_needs = generate_line(tool)
    #     results.extend(polish_needs)
    #
    # with open("dataset_train.json", 'w', encoding="utf-8") as f:
    #     json.dump(results, f, ensure_ascii=False, indent=4)
    generate_false_sentences("../testData/dataset_api_desc_2.json")
