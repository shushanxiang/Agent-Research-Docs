import json

from apis.api_selection_hub import ApiSelectionHub
from models import LargeLanguageModel
from param_extraction.param_extraction_hub import ParamExtractionHub
from tasks import TaskManager,GenerateTaskHub
from tools import ToolSummaryHub, ToolUseHub, ToolManager
from utils import logger, TASK_ERROR_CODE, TASK_SUCCESS_CODE, RESPONSE_STATUS_CODE_SUCCESS, TASK_STATUS_FINISH, \
    TASK_STATUS_RUNNING, TASK_STATUS_WAIT_CONFIRM, TASK_INIT_TOOL_ID, TASK_TYPE_SINGLE, TASK_TYPE_APIS, \
    TASK_TYPE_UNKNOWN, TASK_TYPE_MAINTAIN, GRAPH_TITLE_SUCESS, GRAPH_TITLE_FAILURE, TASK_SYS_OUTPUT_STOP
import traceback

from utils.config import api_result_max_length, api_result_max_threshold


class ApiPlanningHub:
    def __init__(self, milvus_uri, model_path, milvus_db_name, model, temperature, top_p,
                mongo_host, mongo_db, mongo_port, topK, api_url, api_key,executor):
        """
        初始化 ApiPlanningHub 类的实例。

        :param milvus_uri: 连接地址，通常用于指定服务的访问地址
        :param model_path: 模型文件的路径
        :param milvus_db_name: 数据库的名称
        :param model: 使用的LLM名称
        :param temperature: 采样温度，用于控制生成文本的随机性
        :param top_p: 核采样概率，用于控制生成文本的多样性
        :param mongo_host: 主机地址，通常用于数据库或服务的连接
        :param mongo_db: 数据库标识，可能用于指定具体的数据库
        :param mongo_port: 端口号，用于网络连接
        :param topK: 检索时返回的前 K 个结果
        """
        self.api_selection_hub = ApiSelectionHub(milvus_uri, model_path, milvus_db_name, model, temperature, top_p,
                                                mongo_host, mongo_db, mongo_port, api_url, api_key)
        self.topK = topK
        self.param_extraction_hub = ParamExtractionHub(model, temperature, top_p, api_url, api_key)
        self.tool_summary_hub = ToolSummaryHub(model, temperature, top_p, api_url, api_key)
        self.tool_use_hub = ToolUseHub("")
        self.generate_task_hub = GenerateTaskHub(model, temperature, top_p, api_url, api_key, mongo_host, mongo_db, mongo_port, milvus_uri, milvus_db_name)
        self.task_manager = TaskManager(mongo_host, mongo_db, mongo_port)
        self.tool_manager = ToolManager(mongo_host, mongo_db, mongo_port, milvus_uri, milvus_db_name)
        self.executor = executor
        self.llm = LargeLanguageModel(api_url, api_key)
        self.model = model
        self.temperature = temperature
        self.top_p = top_p

    def generate_output(self, text):
        prompt = " 请将以下句子进行润色成通顺的话，请直接输出结果：\n\n\n" + text
        print(prompt)
        result = self.llm.chat_completions(prompt, self.model, self.temperature, self.top_p)
        return result

    @staticmethod
    def _build_query_from_params(params: dict, tool_name: str) -> str:
        """根据修改后的参数和工具名构建最新的查询描述，用于更新 changed_query。

        当用户通过 correct_params 修改参数后，需要将 changed_query 更新为反映最新参数的描述，
        确保后续的 tool_summary prompt 能正确描述当前实际查询的内容。
        """
        # 用参数值替换原始 query 中的核心实体，使摘要生成时能引用正确的查询对象
        param_values = [str(v) for v in params.values() if v is not None]
        if param_values:
            return f"查询{tool_name}，参数：{', '.join(param_values)}"
        return f"调用{tool_name}"

    def _set_task_type(self, query, task_id, task_type, system_output):
        logger.debug(f"用户请求[{query}]生成任务[{task_id}]{system_output}")
        self.task_manager.update_task_recorder(task_id, TASK_STATUS_RUNNING, system_output, task_type=task_type)

    def _update_task_curr_desc(self,task_id,task_desc):
        self.task_manager.update_task_recorder(task_id, TASK_STATUS_RUNNING, "正在为您分析中，请稍等......",
                                                graph_title="正在为您分析中，请稍等......", curr_task_desc=task_desc)

    def _update_task_node_edge(self, task, task_new_result, system_output,is_end=False):
        """
        更新显示的知识图谱推理路径
        :param task: 当前任务的Task实体
        :param task_new_result: 任务的当前结果，结果是个字典，包含以下键值对
                {
                "code": ,
                "result": "",
                "tool": "",
                "missing_param": [],
                "param": [],
                "query": "",
                "task_description": ""
            }
        :param system_output: 输出的信息
        :param is_end: 当前任务是否结束
        """
        try:
            nodes = task.nodes
            sub_nodes = []
            edges = task.edges
            index = len(nodes)
            sub_index = index * 10000
            graph_title = GRAPH_TITLE_SUCESS
            # if system_output == "当前API无法实现用户需求":
            #     self.taskManager.update_task_recorder(task.task_id, TASK_STATUS_FINISH, system_output,  is_end,
            #                                         TASK_TYPE_MAINTAIN,[], [], "异常调用链")
            #     return
            if task_new_result["code"] != TASK_SUCCESS_CODE:
                self.task_manager.update_task_recorder(task.task_id, TASK_STATUS_FINISH, TASK_SYS_OUTPUT_STOP+system_output, graph_title=GRAPH_TITLE_FAILURE)
                return
            nodes.append({
                "id": str(index),
                "name": str(index) + "_" + task_new_result["tool"],
                "label": task_new_result["tool"],
                "group": task_new_result["tool"],
                "task_description": task_new_result["query"],
                "params": json.dumps(task_new_result["param"], ensure_ascii=False),
                "result": json.dumps(task_new_result["result"], ensure_ascii=False),
            })
            if(len(nodes) > 1):
                edges.append(
                    {
                        "source": nodes[index-1]["id"], "target": nodes[index]["id"], "value": '正向API规划', "symbolSize": [5, 20],
                        "label": {"show": False}
                    }
                )
            for param_node in task_new_result["missing_param"]:
                sub_nodes.append({
                    "id": str(sub_index),
                    "name": str(sub_index) + "_" + param_node["tool"],
                    "label": param_node["tool"],
                    "group": param_node["tool"],
                    "task_description": param_node["task_description"],
                    "params": json.dumps(param_node["param"], ensure_ascii=False),
                    "result": json.dumps(param_node["result"], ensure_ascii=False),
                })
                edges.append(
                    {
                        "source": str(sub_index), "target": str(index), "value": '缺省参数逆向API规划',
                        "symbolSize": [5, 20],
                        "label": {"show": False}
                    }
                )
                sub_index += 1

            nodes = nodes + sub_nodes
        except Exception as e:
            logger.error(f"任务{task.task_id}图像绘制错误：{e}，但任务继续进行...\n{traceback.format_exc()}")
            self.task_manager.update_task_recorder(task.task_id, TASK_STATUS_RUNNING, "图像绘制错误，但任务继续进行...", graph_title="图像绘制失败")
            return
        logger.debug(f"任务{task.task_id}保存图像的节点[{nodes}]和边[{edges}]")
        if is_end:
            self.task_manager.update_task_recorder(task.task_id, TASK_STATUS_FINISH, system_output, graph_title, nodes=nodes, edges=edges)
        else:
            self.task_manager.update_task_recorder(task.task_id, TASK_STATUS_RUNNING, system_output, graph_title, nodes=nodes, edges=edges)
        return

    def _not_loop_validate(self, task, cur_task_result, max_steps: int = 15):
        """
        增强版循环检测，覆盖四种场景：
        1. 步数预算：单任务最多 max_steps 步
        2. 状态签名：同一工具+同一结果在最近 4 次调用中重复≥3 次
        3. 工具连续性：连续 3 次调用同一工具
        4. 工具链环路：A→B→C→A 周期检测

        :return: True 表示无循环，False 表示检测到循环
        """
        # ===== 1. 步数预算检查 =====
        if len(task.nodes) >= max_steps:
            logger.warning(f"[循环检测] 任务{task.task_id}超过最大步数{max_steps}，强制终止")
            return False

        # ===== 构建调用链 =====
        api_chains = []
        for node in task.nodes:
            try:
                params = json.loads(node.get("params", "{}"))
            except (json.JSONDecodeError, TypeError):
                params = {}
            api_chains.append({
                "tool": node["label"],
                "result": node.get("result", ""),
                "params": params,
            })
        api_chains.append({
            "tool": cur_task_result["tool"],
            "result": cur_task_result.get("result", ""),
            "params": cur_task_result.get("param", {}),
        })

        # ===== 2. 状态签名检测 =====
        N = 4
        if len(api_chains) >= N:
            recent = api_chains[-N:]
            for item in recent:
                signature = (item["tool"], item["result"])
                count = sum(1 for r in recent if (r["tool"], r["result"]) == signature)
                if count >= 3:
                    logger.warning(f"[循环检测] 状态签名重复: tool={signature[0]}, count={count}")
                    return False

        # ===== 3. 工具连续性 =====
        same_tool_count = 0
        for i in range(len(api_chains) - 1, 0, -1):
            if api_chains[i]["tool"] == api_chains[i - 1]["tool"]:
                same_tool_count += 1
            else:
                break
        if same_tool_count >= 2:
            logger.warning(
                f"[循环检测] 工具连续性循环: {api_chains[-1]['tool']} 连续调用{same_tool_count + 1}次"
            )
            return False

        # ===== 4. 工具链环路检测 =====
        tool_sequence = [c["tool"] for c in api_chains]
        for cycle_len in [2, 3]:
            if len(tool_sequence) >= cycle_len * 2:
                tail = tool_sequence[-cycle_len:]
                prev = tool_sequence[-cycle_len * 2 : -cycle_len]
                if tail == prev:
                    logger.warning(f"[循环检测] 工具链环路: 周期={cycle_len}, 序列={tail}")
                    return False

        return True

    def _supplement_parameters(self, new_query, missing_param):
        """
        补充缺失的参数值。
        该方法根据新的查询语句和缺失的参数名，尝试从工具调用的结果中获取缺失的参数值。
        首先通过 `apiSelectionHub` 获取合适的工具，然后使用 `paramExtractionHub` 提取参数，
        调用工具并解析返回结果，若结果中包含缺失的参数，则返回该参数值和工具名称。
        输入：
            :param new_query: 新的查询语句，用于获取缺失参数的值
            :param missing_param: 缺失的参数名
        :return:
            若找到缺失参数的值，返回参数值和工具名称、汇总响应结果；否则返回3个 None
        """
        #缺失的参数有可能是其他工具调用的结果
        tool = self.api_selection_hub.get_tool_coarse_and_fine(new_query, None, topK=self.topK)
        if tool is None:
            return None, None, None
        params, new_missing_param = self.param_extraction_hub.extraction_params(new_query, tool)
        if len(new_missing_param) != 0:
            return None, None, None

        single_tool_response = self.tool_use_hub.tool_use(tool, params)

        if single_tool_response.status_code != RESPONSE_STATUS_CODE_SUCCESS:
            return None, None, None

        if len(single_tool_response.text) != 0:
            results = json.loads(single_tool_response.text)

            if isinstance(results, list) and len(results) != 0:
                results = results[0]
            if missing_param in results:
                return results[missing_param], tool.name_for_human, {
                    "code": TASK_SUCCESS_CODE,
                    "tool": tool.name_for_human,
                    "result": single_tool_response.text,
                    "param": params,
                    "query": new_query,
                    "task_description": new_query
                }
            else:
                return None, None, None
        else:
            return None, None, None

    def _tool_check(self, tool, task_desc, raw_query):
        """
        对工具的检查，此函数接收工具和用户查询语句

        主要工作：
        1. 检查工具是否缺乏参数。
        2. 结合用户查询语句和工具，检查是否存在提示词注入攻击。
        3. 如工具缺乏参数，借助大模型进行参数的补全。

        :param
            tool: 当前被检查的工具
            task_desc: 输入的查询语句，用于描述用户的需求(由大模型生成和改写)
            raw_query：用户的原始查询
        :return:
            一个字典，包含处理结果的相关信息，
            如状态码code、工具名称tool、结果内容result、缺失参数信息missing_param、参数列表param和任务描述task_description等
        """
        params, missing_params = self.param_extraction_hub.extraction_params(task_desc + " " + raw_query, tool)
        missing_params_supplemented = []
        new_params = params.copy()
        if len(missing_params) == 0:
            # ===== 新增：代码层参数校验（在 LLM 注入检测之前） =====
            from param_extraction.parameter_validator import ParameterValidator
            validation_errors = ParameterValidator.validate(tool, new_params)
            if validation_errors:
                logger.warning(f"[{raw_query}:{task_desc}]代码层参数校验不通过: {'; '.join(validation_errors[:3])}")
                return {
                    "code": TASK_ERROR_CODE,
                    "result": "validation_error",
                    "tool": "参数校验不通过",
                    "missing_param": [],
                    "param": new_params,
                    "query": task_desc,
                    "task_description": (
                        f"参数校验不通过，共{len(validation_errors)}项：\n"
                        + "\n".join(validation_errors)
                    ),
                }
            # ===== 新增结束 =====

            logger.debug(f"[{raw_query}:{task_desc}]未缺失参数，准备安全检查")
            inject_flag, reason = self.generate_task_hub.gen_judge_task(task_desc, tool, new_params)
            if inject_flag:
                return {
                    "code": TASK_ERROR_CODE,
                    "result": "inject",
                    "tool": "异常调用节点-提示注入攻击",
                    "missing_param": [],
                    "param": {},
                    "query": task_desc,
                    "task_description": reason
                }
        else:
            logger.debug(f"[{raw_query}:{task_desc}]缺失参数，进行参数的补齐....")

            for missing_param in missing_params:
                gen_param_query = self.generate_task_hub.gen_param_task(task_desc,
                                                                        json.dumps(params, ensure_ascii=False, indent=4),
                                                        f'{missing_param.name}: {missing_param.description}')
                logger.debug(f"[{task_desc}]参数[{missing_param.name}:{missing_param.description}]生成或补齐任务的描述词为：{gen_param_query}")
                supplement_param, supplement_param_tool, supplement_param_result = self._supplement_parameters(
                    gen_param_query, missing_param.name)
                if supplement_param is not None:
                    logger.debug(f"[{raw_query}:{task_desc}]的缺失参数{missing_param.name}已补充：\n{supplement_param_tool}\n{supplement_param_result}")
                    params[missing_param.name] = supplement_param
                    missing_params_supplemented.append(supplement_param_result)
                else:
                    return {
                        "code": TASK_ERROR_CODE,
                        "result": "missing_param",
                        "tool": "异常调用节点-缺少必要参数",
                        "missing_param": [],
                        "param": {},
                        "query": task_desc,
                        "task_description": f"通过参数补全Query:{gen_param_query} 无法为 {tool.name_for_human} API 补全缺少参数 {missing_param.name}"
                    }

            logger.debug(f"[{raw_query}:{task_desc}]参数已补全，进行参数校验和安全检查")
            # 代码层参数校验 — 补全的参数值来自外部 API 返回结果，类型和范围不受控
            from param_extraction.parameter_validator import ParameterValidator
            validation_errors = ParameterValidator.validate(tool, params)
            if validation_errors:
                logger.warning(f"[{raw_query}:{task_desc}]参数补全后校验不通过: {'; '.join(validation_errors[:3])}")
                return {
                    "code": TASK_ERROR_CODE,
                    "result": "validation_error",
                    "tool": "参数校验不通过",
                    "missing_param": [],
                    "param": params,
                    "query": task_desc,
                    "task_description": f"参数补全后校验不通过，共{len(validation_errors)}项：\n"
                                        + "\n".join(validation_errors)
                }
            inject_flag, reason = self.generate_task_hub.gen_judge_task(task_desc, tool, params)
            if inject_flag:
                return {
                    "code": TASK_ERROR_CODE,
                    "result": "inject",
                    "tool": "异常调用节点-提示注入攻击",
                    "missing_param": [],
                    "param": {},
                    "query": task_desc,
                    "task_description": reason
                }

        return {
            "code": TASK_SUCCESS_CODE,
            "result": "",
            "tool": tool.name_for_human,
            "missing_param": missing_params_supplemented,
            "param": params,
            "query": task_desc,
            "task_description": task_desc
        }


    def api_planning_before_human_feedback(self, task_desc, task_id, raw_query):
        """
        单API规划步骤中人类反馈部分前工作内容。此函数接收一个查询语句，根据查询选择合适的工具。
        如果在处理过程中出现问题或找不到合适的工具，则返回相应的错误信息。

        代码流程：
        1. 通过 `apiSelectionHub` 根据查询语句获取合适的工具。
        2. 若未找到工具，返回包含错误信息的结果。
        3. 若找到工具，使用 `paramExtractionHub` 提取参数和缺失参数。
        5. 若有缺失参数，使用 `generateTaskHub` 生成新查询，调用 `supplement_Parameters` 补充缺失参数。
        6. 若所有缺失参数都补充成功，并返回工具和工具参数；若有缺失参数补充失败，返回错误信息。

        :param
            task_desc: 输入的查询语句，用于描述用户的需求，一般多API时使用
            task_id: 任务ID
            raw_query：用户的原始查询
        :return:
            一个字典，包含处理结果的相关信息，如状态码、工具名称、结果内容、缺失参数信息、参数列表和任务描述等
        """
        tool = self.api_selection_hub.get_tool_coarse_and_fine(task_desc, None, topK=self.topK)

        if tool is None:
            txt = f"您的要求[{raw_query}]未找到合适的工具，请换个问法或问题再试试。"
            logger.warning(txt)
            self.task_manager.update_task_recorder(task_id, TASK_STATUS_FINISH, TASK_SYS_OUTPUT_STOP+txt, graph_title=GRAPH_TITLE_FAILURE)
        else:
            result = self._tool_check(tool, task_desc, raw_query)
            if result["code"] == TASK_SUCCESS_CODE:
                system_output = f'''根据您的查询要求{raw_query}，我发现目前需要使用工具{tool.name_for_human}，
                相关参数是[{result["param"]}]。\n请确认该工具是否正确且立即使用。如果您想停止本次任务执行也请告诉我。
                \n如果该工具正确且立即使用，建议回答‘立即执行’;
                \n如果您想停止本次任务执行，建议回答‘不执行’;
                '''
                self.task_manager.update_task_recorder(task_id, TASK_STATUS_WAIT_CONFIRM, system_output, graph_title="请确认",
                                                        curr_task_desc=task_desc,curr_tool_id=tool.tool_id, curr_tool_param=result["param"])

            else:
                # 失败路径也保存 curr_tool_id + curr_tool_param，确保评估体系能采集到"选了什么工具但被拦截了"
                self.task_manager.update_task_recorder(task_id, TASK_STATUS_FINISH,
                                                       TASK_SYS_OUTPUT_STOP + result["task_description"],
                                                       graph_title=GRAPH_TITLE_FAILURE,
                                                       curr_task_desc=task_desc,
                                                       curr_tool_id=tool.tool_id,
                                                       curr_tool_param=result["param"])

    def api_planning_handle_human_feedback(self, task, human_feedback):
        """
        处理人类反馈信息

        支持 6 种意图：confirm / abort / correct_params / correct_tool / clarify / unrelated
        每次反馈记录审计日志（version + feedback_log）

        :param
            task: 任务实例
            human_feedback: 人类反馈信息
        """
        try:
            from datetime import datetime

            # 获取当前等待确认的工具信息
            curr_tool_id = task.curr_tool_id
            curr_tool_param = dict(task.curr_tool_param) if task.curr_tool_param else {}

            if curr_tool_id == TASK_INIT_TOOL_ID:
                logger.error(f"任务[{task.task_id}]没有等待确认的工具")
                self.task_manager.update_task_recorder(task.task_id, TASK_STATUS_FINISH,
                                                    TASK_SYS_OUTPUT_STOP+"没有等待确认的工具",
                                                    graph_title=GRAPH_TITLE_FAILURE)
                return

            # 获取工具对象
            tool = self.tool_manager.get_tools_by_ids([curr_tool_id])[0]

            # 意图识别（返回结构化 dict）
            intent_result = self._recognize_human_intent(human_feedback, tool, curr_tool_param)
            intent = intent_result["intent"]

            # 构造审计日志基础条目
            feedback_entry = {
                "ts": datetime.utcnow().isoformat(),
                "feedback_raw": human_feedback,
                "intent": intent,
                "confidence": intent_result["confidence"],
                "patch": intent_result.get("patch", {}),
                "state_before": {
                    "tool_id": curr_tool_id,
                    "tool_name": tool.name_for_human,
                    "params": curr_tool_param,
                },
                "state_after": {},
                "action_taken": "",
            }

            if intent == "confirm":
                # ===== 确认执行 =====
                feedback_entry["action_taken"] = "execute"
                feedback_entry["state_after"] = feedback_entry["state_before"]
                self.task_manager.update_task_recorder(task.task_id, TASK_STATUS_RUNNING,
                                                       "正在执行工具调用...",
                                                       feedback_entry=feedback_entry)
                # 重新获取 task（update 后可能已变），执行工具调用
                task = self.task_manager.get_task_by_id(task.task_id)
                if task.task_type == TASK_TYPE_SINGLE:
                    invoke_result = self._process_single_api_invoke(task.raw_query, task, tool, curr_tool_param)
                    if invoke_result["code"] == TASK_ERROR_CODE:
                        self.task_manager.update_task_recorder(task.task_id, TASK_STATUS_FINISH,
                                                                TASK_SYS_OUTPUT_STOP + invoke_result["task_description"],
                                                                graph_title=GRAPH_TITLE_FAILURE)
                        return
                    summary = self.tool_summary_hub.tool_summary(task.changed_query, [invoke_result])
                    self._update_task_node_edge(task, invoke_result, summary, True)
                    logger.info(f"任务[{task.changed_query}]，ID[{task.task_id}]：已完成，任务摘要[{summary}]")
                else:
                    invoke_result = self._process_single_api_invoke(task.curr_task_desc, task, tool, curr_tool_param)
                    result = invoke_result["task_description"]
                    if invoke_result["code"] == TASK_ERROR_CODE:
                        logger.info(f"任务[{task.changed_query}]，ID[{task.task_id}]中止：发生错误，[{result}]")
                        self.task_manager.update_task_recorder(task.task_id, TASK_STATUS_FINISH, result, graph_title="任务错误")
                        return
                    if not self._not_loop_validate(task, invoke_result):
                        logger.info(f"任务[{task.changed_query}]，ID[{task.task_id}]中止：检测到循环调用")
                        invoke_result["code"] = TASK_ERROR_CODE
                        self.task_manager.update_task_recorder(task.task_id, TASK_STATUS_FINISH,
                                                                TASK_SYS_OUTPUT_STOP+"检测到循环调用，系统已自动终止，请尝试更换提问方式",
                                                                graph_title="调用链错误-循环调用")
                        return
                    logger.info(f"任务[{task.changed_query}]，ID[{task.task_id}]：已处理完成子任务{task.curr_task_desc}")
                    self._update_task_node_edge(task, invoke_result, f"已处理完成子任务 {task.curr_task_desc}")

                    # 任务类型为多API调用任务时，继续下一个API调用
                    flag, task_description = self.generate_task_hub.gen_from_context_task(task.changed_query, task.nodes)
                    logger.info(f"任务[{task.changed_query}]，ID[{task.task_id}]：任务是否完成：[{flag}]，后续任务[{task_description}]")
                    if task_description is not None:
                        logger.debug(f"任务[{task.changed_query}]，ID[{task.task_id}]继续，任务描述[{task_description}]入库")
                        self._update_task_curr_desc(task.task_id, task_description)
                        self.api_planning_before_human_feedback(task_description, task.task_id, task.raw_query)
                    if flag and task_description is None:
                        context = self._get_summary_from_nodes(task)
                        summary = self.tool_summary_hub.tool_summary(task.changed_query, context)
                        self.task_manager.update_task_recorder(task.task_id, TASK_STATUS_FINISH, summary, graph_title="任务完成")

            elif intent == "abort":
                # ===== 放弃任务执行 =====
                feedback_entry["action_taken"] = "abort"
                feedback_entry["state_after"] = feedback_entry["state_before"]
                self.task_manager.update_task_recorder(task.task_id, TASK_STATUS_FINISH,
                                                       TASK_SYS_OUTPUT_STOP + "已为您放弃任务执行",
                                                       feedback_entry=feedback_entry)

            elif intent == "correct_params":
                # ===== 修改参数 =====
                patch = intent_result.get("patch", {})
                #Python 中空 dict 的布尔值是 False，空补丁时 not patch 为 True
                if not patch:
                    # 空补丁，降级为 clarify
                    feedback_entry["action_taken"] = "await_clarification"
                    feedback_entry["state_after"] = feedback_entry["state_before"]
                    system_output = (
                        f'您的反馈"{human_feedback}"似乎要修改参数，但未识别到具体修改内容。'
                        f'当前工具是{tool.name_for_human}，参数是{json.dumps(curr_tool_param, ensure_ascii=False)}。'
                        f'请再说明一下要改哪个参数、改成什么值。'
                    )
                    self.task_manager.update_task_recorder(task.task_id, TASK_STATUS_WAIT_CONFIRM,
                                                           system_output, feedback_entry=feedback_entry)
                    return

                # 合并补丁到原参数
                new_params = self._merge_param_patch(curr_tool_param, patch)

                # 代码层参数校验
                from param_extraction.parameter_validator import ParameterValidator
                validation_errors = ParameterValidator.validate(tool, new_params)
                if validation_errors:
                    feedback_entry["action_taken"] = "validation_failed"
                    feedback_entry["state_after"] = {
                        "tool_id": curr_tool_id, "tool_name": tool.name_for_human, "params": new_params
                    }
                    system_output = (
                        f'参数修改后校验不通过：{"; ".join(validation_errors[:3])}。'
                        f'请重新确认参数值。当前参数：{json.dumps(curr_tool_param, ensure_ascii=False)}'
                    )
                    self.task_manager.update_task_recorder(task.task_id, TASK_STATUS_WAIT_CONFIRM,
                                                           system_output, feedback_entry=feedback_entry)
                    return

                feedback_entry["state_after"] = {
                    "tool_id": curr_tool_id, "tool_name": tool.name_for_human, "params": new_params
                }
                feedback_entry["action_taken"] = "reconfirm"
                # 根据修改后的参数更新 changed_query，确保后续执行和摘要使用最新的参数值
                updated_query = self._build_query_from_params(new_params, tool.name_for_human)
                system_output = (
                    f'已根据您的反馈将参数从 {json.dumps(curr_tool_param, ensure_ascii=False)} '
                    f'修改为 {json.dumps(new_params, ensure_ascii=False)}，请确认是否执行。'
                )
                self.task_manager.update_task_recorder(task.task_id, TASK_STATUS_WAIT_CONFIRM,
                                                       system_output, curr_tool_param=new_params,
                                                       changed_query=updated_query,
                                                       feedback_entry=feedback_entry)

            elif intent == "correct_tool":
                # ===== 修改工具/业务对象 =====
                feedback_entry["action_taken"] = "retry_selection"
                feedback_entry["state_after"] = {"tool_id": None, "params": {}}
                # 将 changed_query 更新为用户反馈原文，确保后续执行和摘要使用用户最新选择的查询对象
                self.task_manager.update_task_recorder(task.task_id, TASK_STATUS_RUNNING,
                    f'已根据您的反馈"{human_feedback}"重新选择工具...',
                    changed_query=human_feedback,
                    feedback_entry=feedback_entry)
                # 以用户反馈原文作为查询语句，重新走工具选择流程
                self.api_planning_before_human_feedback(human_feedback, task.task_id, task.raw_query)

            elif intent == "clarify":
                # ===== 提供缺失信息 / 澄清 =====
                feedback_entry["action_taken"] = "await_clarification"
                feedback_entry["state_after"] = feedback_entry["state_before"]
                system_output = (
                    f'您的反馈"{human_feedback}"，我们理解为需要补充信息。'
                    f'当前工具是{tool.name_for_human}，参数是{json.dumps(curr_tool_param, ensure_ascii=False)}。'
                    f'请确认是否执行，或提供更多信息。'
                )
                self.task_manager.update_task_recorder(task.task_id, TASK_STATUS_WAIT_CONFIRM,
                                                       system_output, feedback_entry=feedback_entry)

            else:
                # ===== unclear / unrelated — 意图不明确，继续等待确认 =====
                feedback_entry["action_taken"] = "reask"
                feedback_entry["state_after"] = feedback_entry["state_before"]
                if intent == "unrelated":
                    system_output = (
                        f'您的反馈"{human_feedback}"与当前确认操作似乎无关。'
                        f'当前需要确认是否使用工具{tool.name_for_human}，'
                        f'参数为{json.dumps(curr_tool_param, ensure_ascii=False)}。'
                        f'请明确是否执行，或者告诉我需要修改什么。'
                    )
                else:
                    system_output = (
                        f'您的反馈"{human_feedback}"我们暂时无法理解，请重新确认：'
                        f'当前需要使用工具{tool.name_for_human}，相关参数是{curr_tool_param}，'
                        f'请明确是否执行该工具调用，或者确认放弃本次任务执行。'
                    )
                self.task_manager.update_task_recorder(task.task_id, TASK_STATUS_WAIT_CONFIRM,
                                                       system_output, feedback_entry=feedback_entry)

        except Exception as e:
            logger.error(f"处理人类反馈时发生错误: {e}\n{traceback.format_exc()}")
            self.task_manager.update_task_recorder(task.task_id, TASK_STATUS_FINISH,
                                                   TASK_SYS_OUTPUT_STOP+"处理您的要求时发生系统内部错误，请联系系统管理员",
                                                   graph_title=GRAPH_TITLE_FAILURE)

    def _process_single_api_invoke(self,query,task,tool,params):
        params = dict(params)  # 复制一份，避免 tool_use 原地修改影响 node 写入
        logger.debug(f"[{query}]准备进行工具{tool.operationId}调用,参数为：{params}")
        single_tool_response = self.tool_use_hub.tool_use(tool, params)
        logger.debug(f"[{query}]工具{tool.operationId}调用完成,响应为：{single_tool_response}")
        if single_tool_response.status_code != RESPONSE_STATUS_CODE_SUCCESS:
            result = {
                "code": TASK_ERROR_CODE,
                "result": "",
                "tool": "异常调用节点-调用外部系统失败",
                "missing_param": [],
                "param": params,
                "query": query,
                "task_description": "调用外部系统失败"
            }
        else:
            # 解决调用函数时，返回结果过多的问题
            api_result_length_limit = int(api_result_max_length * api_result_max_threshold)
            api_invoke_result_length = len(single_tool_response.text)
            api_result_fact = single_tool_response.text
            if api_invoke_result_length >= api_result_length_limit:
                logger.warning(f"[{query}]API调用结果长度超出限制，截取长度{api_result_length_limit}...")
                api_result_fact = single_tool_response.text[:api_result_length_limit]
                result_text = f"API调用结果长度为{api_invoke_result_length}超出限制，进行了截取，保留的内容为：{api_result_fact}"
            else:
                result_text = api_result_fact
            logger.debug(f"[{query}]工具实际调用结果：{api_result_fact}")
            result = {
                "code": TASK_SUCCESS_CODE,
                "tool": tool.name_for_human,
                "result": result_text,
                "missing_param": [],
                "param": params,
                "query": query,
                "task_description": query
            }
        logger.debug(f"[{query}]工具{tool.operationId}调用返回值：{result}")
        return result

    def _get_summary_from_nodes(self,task):
        context = []
        nodes = task.nodes
        for node in nodes:
            step = {
                "tool": node["label"],
                "task_description": node["task_description"],
                "result": node["result"]
            }
            context.append(step)
        return context

    def _recognize_human_intent(self, human_feedback, tool, tool_param):
        """
        识别人类反馈意图

        三层策略：
        1. 关键词快速通道（confirm/abort 明确表述，零延迟）
        2. LLM 结构化解析（6 种意图 + confidence + patch）
        3. 降级为 unclear（LLM 失败或功能关闭时）

        :param human_feedback: 人类反馈信息
        :param tool: 当前工具
        :param tool_param: 工具参数
        :return: dict {"intent": str, "confidence": float, "patch": dict, "reason": str}
        """
        from utils.config import enhanced_human_feedback_enabled
        from utils.const import (
            INTENT_CONFIRM, INTENT_ABORT, INTENT_UNCLEAR, VALID_INTENTS
        )
        from prompt.general_prompts import parse_intent_json

        # ===== 第一层：关键词快速通道 =====
        confirm_keywords = ["确认执行", "执行任务", "同意执行", "继续执行", "立即执行"]
        abort_keywords = ["放弃执行", "停止执行", "中止执行", "取消执行", "不执行", "不要执行"]

        feedback_lower = human_feedback.lower()

        for keyword in confirm_keywords:
            if keyword in feedback_lower:
                return {"intent": INTENT_CONFIRM, "confidence": 1.0, "patch": {}, "reason": "关键词匹配: 确认"}

        for keyword in abort_keywords:
            if keyword in feedback_lower:
                return {"intent": INTENT_ABORT, "confidence": 1.0, "patch": {}, "reason": "关键词匹配: 放弃"}

        # ===== 第二层：增强意图识别关闭时直接降级 =====
        if not enhanced_human_feedback_enabled:
            return {"intent": INTENT_UNCLEAR, "confidence": 0.0, "patch": {}, "reason": "增强反馈已关闭"}

        # ===== 第三层：LLM 结构化解析 =====
        try:
            prompt_hub = self.generate_task_hub.PromptModelHub
            prompt = prompt_hub.intent_recognition_prompt(
                human_feedback, tool.name_for_human, tool_param
            )
            llm = self.api_selection_hub.LargeLanguageModel
            response = llm.chat_completions(prompt, self.api_selection_hub.model,
                                            self.api_selection_hub.temperature, self.api_selection_hub.top_p)
            parsed = parse_intent_json(response)
            if parsed and parsed.get("intent") in VALID_INTENTS:
                # 确保返回结构完备
                return {
                    "intent": parsed.get("intent", INTENT_UNCLEAR),
                    "confidence": float(parsed.get("confidence", 0.0)),
                    "patch": parsed.get("patch", {}),
                    "reason": parsed.get("reason", "LLM 识别"),
                }
            logger.warning(f"LLM 意图识别返回无效结果: {str(response)[:200]}")
        except Exception as e:
            logger.error(f"使用大模型识别意图时出错: {e}\n{traceback.format_exc()}")

        return {"intent": INTENT_UNCLEAR, "confidence": 0.0, "patch": {}, "reason": "LLM 解析失败"}

    def _merge_param_patch(self, original_params, patch):
        """将 patch 浅合并到原始参数中，只允许修改已有字段

        :param original_params: 原始参数字典
        :param patch: 用户指定的修改字典
        :return: 合并后的参数字典
        假设系统提示用户确认：
            当前工具：创建订单，参数：{"product": "苹果", "quantity": 10, "price": 5}
            用户回复："把数量改成 20，其他不变"
        则输入
        original_params = {"product": "苹果", "quantity": 10, "price": 5}
        patch           = {"quantity": 20}
        通过for循环，merged["quantity"] = 20
        """
        merged = dict(original_params) if original_params else {}
        for key, value in patch.items():
            #原始参数里有的字段才允许用 patch中的值覆盖
            if key in merged:
                merged[key] = value
            else:
                logger.warning(f"patch 包含非 Schema 字段 '{key}'，已忽略")
        return merged

    def apis_planning(self, query, task_id):
        """
        多API规划函数，用于处理单个或多个查询的API调用流程。
        此函数接收一个查询语句，根据查询判断是否为单任务。若为单任务，直接调用单API规划函数；
        若为多任务，则循环调用单API规划函数，直到任务处理完成。最终返回API调用结果链。

        代码流程：
        1. 调用 `generateTaskHub.gen_root_task` 判断是否为单任务并获取根任务描述。
        2. 若为单任务，调用 `single_api_planning` 处理并将结果添加到结果链中。
        3. 若为多任务，进入循环，不断调用 `single_api_planning` 处理任务，
        并通过 `generateTaskHub.gen_task_from_context` 判断是否还有后续任务。
        4. 若最后还有剩余任务描述，再次调用 `single_api_planning` 处理并添加到结果链中。
        5. 返回完整的API调用结果链。

        :param
            query:输入的查询语句，用于用户描述的需求
            task_id:当前任务内部编号
        :return:
            一个列表，包含一个或多个字典，每个字典表示一次API调用的处理结果，
            包含状态码、工具名称、结果内容、缺失参数信息、参数列表和任务描述等
        """

        is_single_task, root_task_description = self.generate_task_hub.gen_root_task(query)
        logger.debug(f"系统初始处理[{query}]，is_single_task={is_single_task},任务描述为：{root_task_description}")
        if is_single_task:
            self._set_task_type(query, task_id, TASK_TYPE_SINGLE, f"系统判定[{query}]为单工具调用任务")
            self.api_planning_before_human_feedback(query, task_id, query)
        else:
            self._set_task_type(query, task_id, TASK_TYPE_APIS, f"系统判定[{query}]多工具调用任务")
            self.api_planning_before_human_feedback(root_task_description, task_id, query)
        return