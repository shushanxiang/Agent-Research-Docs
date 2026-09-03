"""
LLM 调用工具
============
DashScope SDK 统一封装：通义千问调用 + 优雅降级。
所有 LLM 入口集中于此处，其他模块通过调用此模块间接使用 LLM。
"""

import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

_DASHSCOPE_AVAILABLE = False
try:
    from http import HTTPStatus
    from dashscope import Generation
    _DASHSCOPE_AVAILABLE = True
except ImportError:
    pass


def is_llm_available() -> bool:
    """检测 DashScope SDK 是否可用"""
    return _DASHSCOPE_AVAILABLE


def call_qwen(
    messages: list,
    model: str = "qwen-max",
    temperature: float = 0.2,
    max_tokens: int = 2048,
) -> Optional[str]:
    """
    调用通义千问模型，返回文本响应。

    Args:
        messages: 标准对话消息列表 [{"role":"user","content":"..."}]
        model: 模型名 (qwen-max / qwen-turbo / qwen-plus)
        temperature: 生成温度，越低越确定
        max_tokens: 最大输出 token 数

    Returns:
        模型回答文本；失败时返回 None
    """
    if not _DASHSCOPE_AVAILABLE:
        logger.warning("dashscope SDK not installed, LLM call skipped")
        return None

    try:
        resp = Generation.call(
            model=model,
            messages=messages,
            result_format="message",
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if resp.status_code == HTTPStatus.OK:
            return resp.output.choices[0].message.content
        else:
            logger.error(f"LLM call failed: HTTP {resp.status_code} — {resp.message}")
            return None
    except Exception as e:
        logger.error(f"LLM call exception: {e}")
        return None


def call_qwen_json(
    messages: list,
    model: str = "qwen-turbo",
    temperature: float = 0.1,
) -> Optional[dict]:
    """
    调用通义千问并解析 JSON 响应。

    自动清理响应中的 markdown 代码块包裹。

    Returns:
        解析后的 dict；失败时返回 None
    """
    text = call_qwen(messages, model=model, temperature=temperature)
    if not text:
        return None

    try:
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return json.loads(text)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"LLM JSON parse failed: {e}")
        return None


def extract_metadata_by_llm(document_text: str) -> dict:
    """
    使用 LLM 从建筑文档内容中提取元数据。

    回退：LLM 不可用时返回空 dict。
    """
    prompt = f"""你是一位建筑行业文档专家。请从以下文档内容中提取元数据，以严格 JSON 格式返回：

文档内容：
{document_text[:1500]}

需要提取的字段（不确定的用 null）：
- doc_type: 文档类型（规范/图集/变更单/图纸/报告/施工日志）
- title: 文档标题
- standard_code: 标准编号（如 GB 55037-2022）
- issue_date: 发布日期 YYYY-MM-DD
- effective_date: 施行日期 YYYY-MM-DD
- status: 规范状态（有效/废止/即将废止）
- publisher: 发布单位
- keywords: 3-5 个核心关键词

只返回 JSON，不要其他文字。"""

    result = call_qwen_json(
        [{"role": "user", "content": prompt}],
        model="qwen-turbo",
        temperature=0.1,
    )
    return result or {}


def rerank_by_llm(query: str, candidates: list, top_k: int) -> list:
    """
    使用 LLM 对候选 chunk 进行相关性精排。

    Args:
        query: 用户查询
        candidates: 候选列表 [(score, chunk), ...]
        top_k: 返回数量

    Returns:
        重排后的 [(score, chunk), ...]
    """
    if not candidates:
        return []

    items_text = ""
    for idx, (_, chunk) in enumerate(candidates):
        cid = chunk.get("metadata", {}).get("clause_id", str(idx))
        content = chunk.get("content", "")[:100]
        items_text += f"[{idx}] 条款{cid}: {content}\n"

    prompt = f"""请根据用户查询的相关度，对以下条款进行排序。返回最相关 {top_k} 条的索引编号（从最相关到最不相关），格式如: [3, 0, 5]

查询: {query}

候选条款:
{items_text}

只返回 JSON 数组，如 [3, 0, 5]，不要其他文字。"""

    ids = call_qwen_json(
        [{"role": "user", "content": prompt}],
        model="qwen-turbo",
        temperature=0,
    )

    if not ids or not isinstance(ids, list):
        return [(c[0], c[1]) for c in candidates[:top_k]]

    ranked = []
    for i in ids:
        if 0 <= i < len(candidates):
            ranked.append((candidates[i][0] + 0.5, candidates[i][1]))

    # 追加未排入的
    for idx, (s, c) in enumerate(candidates):
        if idx not in ids:
            ranked.append((s, c))

    return ranked[:top_k]
