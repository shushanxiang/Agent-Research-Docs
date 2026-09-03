# -*- coding: utf-8 -*-
from graph.state import AgentState, get_last_content
from utils.llm_client import call_llm
import re

DEFAULT_LISTING = "这是一个示例标题\n这是五点描述\n这是产品描述\n关键词：A,B,C"
_LISTING_MARKERS = ("标题", "Title", "五点", "Bullet", "描述", "Description", "关键词", "Keywords")


def _extract_listing_from_query(query: str):
    """从消息文本中提取评估对象：若包含 标题/五点/描述/关键词 等标记则整段作为评估对象"""
    if not query:
        return None
    if any(marker in query for marker in _LISTING_MARKERS):
        return query
    return None


def _parse_listing(listing_text: str) -> dict:
    """从 Listing 文本解析 标题/五点/描述/关键词（兼容中英文标记、单行/多行）"""
    result = {"title": "", "bullets": [], "description": "", "keywords": []}
    if not listing_text:
        return result

    # 标题：标题/Title 后到第一个分隔符（逗号/句号/分号/换行）
    m = re.search(r"(?:标题|Title)\s*[:：]\s*([^，。,.;；\n]+)", listing_text, re.I)
    if m:
        result["title"] = m.group(1).strip()

    # 五点：五点/Bullet 到 描述/Description 之间，按序号/换行/分号拆分
    m = re.search(r"(?:五点|Bullet\s*Points?)\s*[:：]\s*(.*?)(?:描述|Description|$)", listing_text, re.I | re.DOTALL)
    if m:
        block = m.group(1)
        bullets = [b.strip() for b in re.split(r"\d+[\.、\)]\s*|[\n;；。]", block) if b.strip()]
        result["bullets"] = bullets

    # 描述：描述/Description 到 关键词/Keywords
    m = re.search(r"(?:描述|Description)\s*[:：]\s*(.*?)(?:关键词|Keywords|$)", listing_text, re.I | re.DOTALL)
    if m:
        result["description"] = m.group(1).strip()

    # 关键词：关键词/Keywords 之后，逗号分隔
    m = re.search(r"(?:关键词|Keywords)\s*[:：]\s*(.*?)$", listing_text, re.I | re.DOTALL)
    if m:
        result["keywords"] = [k.strip() for k in m.group(1).split(",") if k.strip()]

    return result


def evaluator_node(state: AgentState) -> dict:
    """Listing 质量评估：标题/五点/描述/关键词/图片 各20分"""
    # 评估对象优先级：state.target_listing → 消息文本中携带的Listing → 默认示例
    listing_text = state.get("target_listing")
    if not listing_text:
        user_query = get_last_content(state)
        listing_text = _extract_listing_from_query(user_query)
    if not listing_text:
        listing_text = DEFAULT_LISTING

    parsed = _parse_listing(listing_text)

    # 1. 规则分（简单）
    score_detail = {}

    # 标题（20分）：长度10-200字符，含关键词
    title = parsed["title"]
    title_score = 0
    if 10 <= len(title) <= 200:
        title_score += 10
    else:
        title_score += 5
    if any(kw in title.lower() for kw in ["eco", "natural", "light", "durable"]):  # 示例关键词
        title_score += 10
    else:
        title_score += 5
    score_detail["title"] = min(20, title_score)

    # 五点（20分）：至少有5条，每条不短于10词
    bullets = parsed["bullets"]
    bullet_score = min(20, len([b for b in bullets if len(b.split()) > 5]) * 4)
    score_detail["bullet_points"] = min(20, bullet_score)

    # 描述（20分）：长度 > 100词
    desc = parsed["description"]
    desc_score = 20 if len(desc.split()) > 80 else 10
    score_detail["description"] = desc_score

    # 关键词（20分）：至少5个，逗号分隔
    kws = parsed["keywords"]
    kw_score = min(20, len(kws) * 4)
    score_detail["keywords"] = min(20, kw_score)

    # 图片（20分）：假设有图片URL即为满分（简化）
    image_url = state.get("current_image_url") or ""  # 兼容 None 值
    has_image = "http" in listing_text or "image" in image_url
    score_detail["image_quality"] = 20 if has_image else 10

    total = sum(score_detail.values())

    # 2. LLM生成改进建议
    suggestion_prompt = f"当前Listing评分如下：{score_detail}，总分为{total}。请给出3条具体的改进建议（每条不超过20字）。"
    llm_advice = call_llm(suggestion_prompt)
    if llm_advice.startswith("LLM调用失败"):
        # LLM 不可用（如 API 额度耗尽）：给默认建议，不把错误文本当建议展示
        suggestions = ["LLM 服务暂不可用，请检查 API 额度或稍后重试。"]
    else:
        suggestions = llm_advice.split("\n")[:3]

    return {"execution_result": {
        "type": "evaluate",
        "score": total,
        "detail": score_detail,
        "suggestions": suggestions
    }}
