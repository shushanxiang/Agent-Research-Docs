from prompt import PromptModelHub
from utils import logger


class QwenModelPromptHub(PromptModelHub):

    # ===== Qwen 专用 Prompt 覆盖版本号 =====
    # 每个版本号对应一个 Qwen 类实际覆盖的父类方法
    # 未覆盖的方法继承父类的 VERSION_XXX，此处不重复声明
    VERSION_QWEN_ROOT_TASK = "v1.0"              # 覆盖 get_root_task_prompt_text
    VERSION_QWEN_PARAM_TASK = "v1.0"             # 覆盖 get_param_task_prompt_text
    VERSION_QWEN_SUBTASK_CONTEXT = "v1.0"        # 覆盖 gen_subtask_context_prompt
    VERSION_QWEN_PARAM_EXTRACTION = "v1.0"       # 覆盖 get_all_parameters_prompt_text

    def __init__(self, system_prompt,model_name):
        self.system_prompt = system_prompt
        self.stop_label = None
        self.use_desc = f"使用{model_name}模型提示词===>"

    def get_root_task_prompt_text(self):
        logger.info(self.use_desc)
        return """
        You are an excellent API tool planning expert, and I will provide you with user requests and a list of tools.
        Please determine whether to complete the request as a multi API tool task based on user requests and tool list, which requires calling multiple APIs, or as a single API tool task that only requires calling a single API.
        Please note that usually, atomic information query is a single-tool task.
        Usually, querying information about a single product, order, or logistics supplier is a single-tool task
        Creating a single order and adding a single product are tasks that can be completed using a single tool.

        The tool list is as follows:[
        {tool_descs}
        ]

        Reply in JSON format, no other text:
        {{{{ "is_single": true, "description": "" }}}}

        Rule:
        - is_single: true 表示单API工具任务, false 表示多API工具任务
        - description: 当 is_single=false 时，提供用自然语言描述的第一个子任务请求语句来找到相应的API；is_single=true 时填空字符串

        Example1:
        User Request: 先分别查询苹果和梨子的产品信息，再分别查询产品ID为3的产品信息
        Example1 Output:
        {{{{ "is_single": false, "description": "查询苹果的产品信息" }}}}

        User Request: {query}
        """
        #
        # 以上提示词的大致中文含义：
        # '''你是一个优秀的API工具规划专家，我会为你提供用户需求。您需要首先确定是将请求作为需要调用多个API的多API工具任务来完成，还是作为只需要调用单个API的单API工具任务来完成。
        # 如果是单个API工具任务，请回答‘是’；如果是多API工具任务，请回答‘否’，并提供用自然语言描述的第一个子任务请求语句，以找到相应的API。
        # 请注意，通常，原子信息查询是单工具任务。
        # 通常，查询单个产品、订单或物流供应商的信息是一项单一工具的任务
        # 创建单个订单和添加单个产品是可以使用单个工具完成的任务。
        #
        # 回复格式如下:
        # 单一API工具任务:是/否
        # 第一个子任务描述:用自然语言描述的一个子任务，用来寻找相应的API
        #
        # 示例1:
        # 用户请求:先分别查询苹果和梨子的产品信息,再分别查询产品身份证明为3的产品信息
        #
        # 示例1输出:
        # 单一API工具任务:否
        # 第一个子任务描述:查询苹果的产品信息
        #
        # 用户请求:{query}
        # 请直接输出答案，不要输出思维过程！'''
        #

    def get_param_task_prompt_text(self):
        logger.info(self.use_desc)
        return """
        You are an excellent API tool invocation master. I will provide you with the extraction status of the original request and the current API request parameters.
        Please generate a natural language description of the query subtask for the missing parameters. The extracted parameters and parameter values should not appear in the statement, and the statement should include necessary query conditions to find the appropriate API

        Please follow the following rules:
        1. The generated query subtask should be described according to the information of XX in the XX query.For example, when there is a lack of information about the logistics supplier ID, please generate "请查询XXX的物流供应商信息" according to the user's request, where XXX generates a targeted attributive based on the user's request.

        Example1:

        Original request:  创建一个产品ID为21，数量为109，配送区域为南京的订单
        Current parameter extraction:
            "quantity": 109,
            "supplierId": "",
            "productId": 21,
            "orderRegion": "南京"

        Missing parameters: supplierId: 物流供应商Id

        Example1 output:
        请查询能够配送南京的物流供应商信息


        Now I will give you the problem to be solved. Please solve it according to the example and rules

        Original request: {query}
        Current parameter extraction: {params}
        Missing parameters: {missing_param}

        Please output natural language description query statement directly, no need to output the thought process.
            """
        #
        # 以上提示词的大致中文含义：
        # '''您是一位优秀的API工具调用大师。我将向您提供原始请求的提取状态和当前API请求参数。
        # 请为缺失的参数生成查询子任务的自然语言描述。提取的参数和参数值不应出现在语句中，并且语句应包括必要的查询条件以查找适当的API
        #
        # 请遵守以下规则：
        # 1.生成的查询子任务应根据XX查询中的XX信息进行描述。例如，当缺少物流供应商ID的信息时，请生成"查询XXX的物流供应商信息"根据用户的请求，XXX基于用户的请求生成目标属性。
        # 示例1：
        # 原始请求：创建一个产品ID为21，数量为109，配送区域为南京的订单
        # 当前参数提取：
        # "数量"：109，
        # "supplierId"："",
        # "产品ID"：21，
        # "orderRegion"："南京"
        # 缺少参数：supplierId:物流供应商Id
        #
        # 示例1输出：
        # 请查询能够配送南京的物流供应商信息
        #
        # 现在，我将为您呈现待解决的问题。请根据示例和规则解决
        # 原始请求：{query}
        # 当前参数提取：{params}
        # 缺少参数：{missing_param}
        #
        # 请直接输出自然语言描述查询语句，无需输出思维过程。
        #  '''
        #

    def gen_subtask_context_prompt(self, query, context):
        """
        生成用于子任务上下文的提示词。
        该函数根据输入的用户请求和已调用API的上下文信息，生成一个提示词，用于询问模型当前任务是否已完成。
        如果输入的请求为空，则返回停止标签。
        参数:
            query (str): 用户输入的请求内容。
            context (str): 已调用API的上下文信息。
        返回:
            str: 生成的提示词字符串；如果query为空，则返回 self.stop_label。
        """
        logger.info(self.use_desc)
        REACT_PROMPT = """
        You are an outstanding expert in API tool planning, and I will provide a user request that may require calling multiple APIs to complete.
        At the same time, I will also provide contextual information about the API that has been called so far.
        Please determine whether the request has been completed based on the existing context.
        If completed, please reply with 'Yes'; If not completed, please reply with 'No' and provide the next subtask request statement described in natural language to find the corresponding API.

        Please note that if a suitable API is selected and the API call returns normally with actual data, the subtask should be considered completed. However, if the API result explicitly indicates that the requested entity does not exist (e.g., empty result "[]", "not found", "不存在"), and subsequent subtasks depend on a valid result from this step, the entire task should be considered complete as "information not found".

        Please note that subtasks must be executed strictly in the order described in the user request. Do not skip remaining steps after completing the current one, unless a prerequisite failure (e.g., the data required for the next step does not exist) makes further execution impossible. Always check the user's full request to determine if there are additional steps remaining.

        Reply in JSON format, no other text:
        {{{{ "is_single": true, "description": "" }}}}

        Rule:
        - is_single: true 表示任务已完成, false 表示还有后续子任务
        - description: 当 is_single=false 时，提供用自然语言描述的下一个子任务请求语句；is_single=true 时填空字符串

        User Request: {query}

        API Context:
        {context}
        """
        #
        # 以上提示词的大致中文含义：
        # '''您是API工具规划方面的杰出专家，我将提供一个可能需要调用多个API才能完成的用户请求。
        # 同时，我还将提供到目前为止调用的API的上下文信息。
        # 请根据现有上下文确定请求是否已完成。
        # 如果已完成，请回答"是"；如果未完成，请回答"否"，并提供用自然语言描述的下一个子任务请求语句，以查找相应的API。
        # 请注意，如果为子任务选择了合适的API，并且API调用正常返回，即使API调用结果指示查询结果不存在，例如返回空列表"[]"或返回信息不存在，该任务仍应被视为已完成，并且完成结果应被认为信息不存在或为空。
        # 请注意，不同的子任务之间不存在依赖关系，即上一个子任务的API输出内容独立于下一个子任务内容
        #
        # 回复格式如下：
        # 任务是否已完成：是/否
        # 下一个子任务请求：用自然语言描述的下一个子任务请求语句，用于查找相应的API。
        #
        # 现在，我将为您呈现待解决的问题。请根据示例和规则解决
        #
        # 用户请求：{query}
        # API上下文：
        # {context}
        #
        # 请直接输出答案，不要输出思维过程！
        #  '''
        #
        API_CONTEXT_DESC = """
        SubTask{index}: {task_description}
        API{index}: {api_description}
        API{index} Response: {api_response}
        """

        if len(query) == 0:
            return self.stop_label

        index = 1
        apis = ""
        for tmp in context:
            api = API_CONTEXT_DESC.format(index=str(index), api_description=tmp["label"],
                                    api_response=tmp["result"], task_description=tmp["task_description"])
            apis += api
            index += 1

        prompt = REACT_PROMPT.format(query=query, context=apis)
        logger.debug(f"[{query}]子任务上下文提示词: {prompt}")
        return prompt


    def get_all_parameters_prompt_text(self):
        logger.info(self.use_desc)
        return '''Answer the following questions as best you can.

        Extract the arguments: {arguments}
        Format the arguments as a JSON object
        You must obey: the key of the JSON must be exactly the same as the argument name I gave it (must follow the original format)
        You must obey: the extracted arguments be words that appear in the original text of the question
        You must obey: When extracting the product name parameter, there is no need to include the word "产品"
        You must obey: if the format of param is "date-time",please follow the example "2025-08-12T13:58:04.094Z"
        You must obey: if the format of param is "enum"， Please select one from the enum list as the parameter value
        CRITICAL: If you cannot find a clear, explicit value for a required parameter in the original question text, you MUST set it to an empty string "". NEVER guess, infer, or fill placeholder values like 0, -1, "默认", or "未知". An empty string tells the system the parameter is missing and triggers the correct fallback process. Guessing values leads to wrong API calls.

        Use the following format:
        {output}
        Question:{query}
        '''
        #
        # 以上提示词的大致中文含义：
        # '''尽你所能回答以下问题。
        # 提取参数：{arguments}
        # 将参数格式化为JSON对象
        # 您必须遵守：JSON的键必须与我给它的参数名称完全相同（必须遵循原始格式）
        # 您必须遵守：提取的参数是问题原始文本中出现的单词
        # 您必须遵守：提取产品名称参数时，不需要包含"产品"一词
        # 您必须遵守：如果参数的格式为"日期时间"，请按照示例"2025-08-12T13:58:04.094Z"
        # 必须遵守：如果参数的格式为"enum"，请从枚举列表中选择一个作为参数值
        #
        # 使用以下格式：
        # {输出}
        # 问题：{query}
        #  '''
        #
