# -*- coding: utf-8 -*-
from graph.state import AgentState, get_last_content
from utils.llm_client import call_llm
import json
import re

SUPERVISOR_EXAMPLES = """参考示例：
1. 用户：展示7月每日总销售额趋势图 → {"intent":"data","data_type":"trend","need_image":false}
2. 用户：列出库存低于50的SKU及库存数 → {"intent":"data","data_type":"list","need_image":false}
3. 用户：按品类统计7月份的总销量和平均广告费 → {"intent":"data","data_type":"stat","need_image":false}
4. 用户：哪个SKU销售额最高？帮我查一下 → {"intent":"data","data_type":"stat","need_image":false}
5. 用户：分析一下食品类在7月下半月的销售趋势 → {"intent":"data","data_type":"trend","need_image":false}
6. 用户：上传这张产品图，生成三种风格的英文Listing → {"intent":"listing","data_type":null,"need_image":true}
7. 用户：评估这条Listing的质量：标题：... 五点：... → {"intent":"evaluate","data_type":null,"need_image":false}
8. 用户：基于主图生成4张不同场景的产品图 → {"intent":"image","data_type":null,"need_image":true}
9. 用户：帮我看看数据 → {"intent":"data","data_type":"vague","need_image":false}
10. 用户：预测下个月哪个品类销量最高 → {"intent":"data","data_type":"predict","need_image":false}"""


def _parse_supervisor_output(resp: str) -> dict:
    """从 LLM 返回中解析意图 JSON，失败返回空 dict"""
    m = re.search(r"\{.*\}", resp, re.DOTALL)
    if not m:
        return {}
    try:
        parsed = json.loads(m.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _guess_data_type(query: str):
    """规则兜底：根据关键词推断 data_type（用于 LLM 误判/降级时修正）"""
    if any(k in query for k in ["预测", "预估", "未来", "下个月", "下月"]):
        return "predict"
    if any(k in query for k in ["趋势", "走势", "随时间", "变化", "图"]):
        return "trend"
    if any(k in query for k in ["列出", "哪些", "多少", "清单", "明细", "低于", "高于"]):
        return "list"
    if any(k in query for k in ["统计", "汇总", "最高", "最低", "平均", "对比", "总和", "总销量", "总销售额", "销售额"]):
        return "stat"
    return None


def supervisor_node(state: AgentState) -> dict:
    """意图识别：结构化 JSON 输出 intent / data_type / need_image（含规则兜底）"""
    query = get_last_content(state)
    has_image = bool(state.get("current_image_url"))

    prompt = f"""你是一个意图识别器。分析用户问题，仅输出一个 JSON 对象（不要输出任何其他内容）：
{{"intent": "data"|"listing"|"image"|"evaluate", "data_type": "trend"|"stat"|"list"|"predict"|"vague"|null, "need_image": true|false}}

意图定义：
- data: 数据查询、趋势、图表、统计、预测、查看数据
- listing: 生成文案、标题、五点描述、产品描述、Listing
- image: 生成图片、产品图、场景图
- evaluate: 评分、评估、质量、改进建议

data_type（仅当 intent 为 data 时填写，否则为 null）：
- trend: 趋势、走势、随时间变化
- stat: 统计、汇总、最高/最低、对比、平均
- list: 列出、哪些、多少、清单、明细
- predict: 预测、预估、未来
- vague: 只是模糊地查看数据，没有具体统计目标

need_image：用户明确提到上传图片/主图/这张图并用于任务时 → true；其余 false。
（当前会话是否已有图片：{"是" if has_image else "否"}）

{SUPERVISOR_EXAMPLES}
用户问题：{query}
输出JSON："""

    resp = call_llm(prompt, system_prompt="你是一个意图识别器，只输出JSON，不要输出其他内容。", temperature=0.1)
    parsed = _parse_supervisor_output(resp)

    intent = parsed.get("intent") if parsed.get("intent") in ("data", "listing", "image", "evaluate") else "data"
    data_type = parsed.get("data_type") if parsed.get("data_type") in ("trend", "stat", "list", "predict", "vague") else None
    need_image = bool(parsed.get("need_image", False))

    # 规则兜底：LLM 降级/误判为 vague 时，若 query 含明确任务词则按规则修正 data_type
    if intent == "data" and data_type == "vague":
        guessed = _guess_data_type(query)
        if guessed:
            data_type = guessed

    return {"intent": intent, "data_type": data_type, "need_image": need_image}
