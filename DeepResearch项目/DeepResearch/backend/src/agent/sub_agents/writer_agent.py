"""WriterAgent sub-graph with debate-loop refinement.

Encapsulates the report-writing pipeline with iterative Critic ↔ Writer revision:
  1. outline         — design chapter structure
  2. draft           — write (or revise) content
  3. critic_review   — score the draft and return structured feedback
  4. cite_and_polish — replace short URLs, deduplicate sources, final polish

The debate loop (draft ↔ critic_review) repeats until the Critic is satisfied
(ready_for_polish=True) or max_revisions is reached.
"""

from __future__ import annotations

import json

from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from loguru import logger

from agent.base_agent import Agent, JsonAgent
from agent.configuration import Configuration
from agent.post import Post
from agent.prompts import (
    critic_review_instructions,
    draft_instructions,
    get_current_date,
    outline_instructions,
    polish_instructions,
)
from agent.state import OverallState
from agent.tools_and_schemas import CritiqueResult
from agent.utils import get_research_topic

load_dotenv()

_OUTLINE = "outline"
_DRAFT = "draft"
_CRITIC_REVIEW = "critic_review"
_CITE_AND_POLISH = "cite_and_polish"

# ── constants ──────────────────────────────────────────────────────────
DEFAULT_MAX_REVISIONS = 3


# ═══════════════════════════════════════════════════════════════════════
# Node implementations
# ═══════════════════════════════════════════════════════════════════════

async def _outline(state: OverallState, config: RunnableConfig) -> dict:
    """Generate a structured report outline from the research topic and plan."""
    configurable = Configuration.from_runnable_config(config)
    reasoning_model = state.get("reasoning_model") or configurable.answer_model
    logger.info(f"[WriterAgent] outline 准备使用模型={reasoning_model}")

    agent = Agent(model_id=reasoning_model)
    agent.set_step_prompt(outline_instructions)
    raw = await agent.astep(
        research_topic=get_research_topic(state["messages"]),
        research_proposal=state.get("plan", ""),
        summaries="\n---\n\n".join(state["web_search_result"]),
    )
    outline = Post.extract_pattern(raw, pattern="markdown")
    logger.info(f"[WriterAgent] outline generated ({len(outline)} chars)")
    return {
        "report_outline": outline,
        "revision_count": 0,
        "max_revisions": DEFAULT_MAX_REVISIONS,
    }


async def _draft(state: OverallState, config: RunnableConfig) -> dict:
    """Draft (or revise) the full report following the outline.

    On first pass (no feedback), writes from scratch.
    On revision passes, incorporates the Critic's structured feedback and
    increments the revision counter.
    """
    configurable = Configuration.from_runnable_config(config)
    reasoning_model = state.get("reasoning_model") or configurable.answer_model
    logger.info(f"[WriterAgent] _draft 准备使用模型={reasoning_model}")
    feedback = state.get("critic_feedback", "")
    outline_text = state.get("report_outline", "")
    is_revision = bool(feedback)
    revision = state.get("revision_count", 0) + (1 if is_revision else 0)

    if is_revision:
        logger.info(f"[WriterAgent] revising draft (revision {revision})")
        revision_context = (
            f"\n# 修订说明 (第 {revision} 次修订)\n"
            f"请根据以下审稿意见修改上一版草稿：\n\n"
            f"{feedback}\n\n"
            f"请逐条处理上述问题，优先修复 critical 和 major 级别的问题。"
            f"保留上版草稿中审稿人没有异议的内容。\n"
        )
        return_update = {"revision_count": revision, "critic_feedback": ""}
    else:
        logger.info(f"[WriterAgent] drafting from scratch")
        revision_context = ""
        return_update = {}

    agent = Agent(model_id=reasoning_model)
    agent.set_step_prompt(draft_instructions)
    raw = await agent.astep(
        current_date=get_current_date(),
        research_topic=get_research_topic(state["messages"]),
        research_proposal=state.get("plan", ""),
        outline=outline_text,
        summaries="\n---\n\n".join(state["web_search_result"]),
        revision_context=revision_context,
    )
    draft = Post.extract_pattern(raw, pattern="markdown")
    logger.info(f"[WriterAgent] draft generated ({len(draft)} chars)")
    return {**return_update, "report_draft": draft}


async def _critic_review(state: OverallState, config: RunnableConfig) -> dict:
    """Critic reviews the draft and returns structured feedback.

    Uses JsonAgent with CritiqueResult schema for structured output.
    """
    configurable = Configuration.from_runnable_config(config)
    reasoning_model = state.get("reasoning_model") or configurable.answer_model
    logger.info(f"[WriterAgent] critic reviewing draft 准备使用模型={reasoning_model}")

    draft_text = state.get("report_draft", "")

    agent = JsonAgent(model_id=reasoning_model, keys=CritiqueResult)
    agent.set_step_prompt(critic_review_instructions)
    result = await agent.astep(
        research_topic=get_research_topic(state["messages"]),
        research_proposal=state.get("plan", ""),
        summaries="\n---\n\n".join(state["web_search_result"]),
        draft=draft_text,
    )
    if not isinstance(result, CritiqueResult):
        logger.warning(
            f"[WriterAgent] 审稿模型调用失败（返回类型={type(result).__name__}），"
            f"跳过审稿直接进入润色"
        )
        return {
            "critic_feedback": "",
            "critic_score": 8.0,
            "ready_for_polish": True,
        }

    # Format critique feedback for the Writer's revision pass
    if result.issues:
        issues_text = "\n".join(
            f"- [{iss.severity.upper()}] {iss.location}: {iss.problem}\n"
            f"  建议: {iss.suggestion}"
            for iss in result.issues
        )
    else:
        issues_text = "无明显问题。"

    feedback = (
        f"## 审稿评分: {result.overall_rating}/10\n"
        f"## 综合评价: {result.summary}\n\n"
        f"## 具体问题:\n{issues_text}"
    )

    logger.info(
        f"[WriterAgent] critic score={result.overall_rating}/10, "
        f"issues={len(result.issues)} "
        f"(critical={sum(1 for i in result.issues if i.severity=='critical')}, "
        f"major={sum(1 for i in result.issues if i.severity=='major')}, "
        f"minor={sum(1 for i in result.issues if i.severity=='minor')}), "
        f"ready_for_polish={result.ready_for_polish}"
    )

    return {
        "critic_feedback": feedback,
        "critic_score": result.overall_rating,
        "ready_for_polish": result.ready_for_polish,
    }


def _route_after_critic(state: OverallState, config: RunnableConfig) -> str:
    """决定：继续修改或进入终审润色。

    三重退出保险（设计理由：不能完全信任 LLM Critic 的自评，
    Critic 和 Writer 可能共用同一模型，存在"自己审自己"的偏差）：

      1. Critic 明确标记 ready_for_polish — LLM 判断质量合格
      2. critic_score >= 8.0 — 质量达标，即使 Critic 标记未 ready 也提前退出
      3. critic_score >= 6.0 且 revision_count >= 1 — 至少改过一次且评分及格
      4. revision_count >= max_revisions — 安全兜底，强制退出

    否则回到 draft 继续修改。
    """
    revision = state.get("revision_count", 0)
    max_rev = state.get("max_revisions", DEFAULT_MAX_REVISIONS)
    ready = state.get("ready_for_polish", False)
    score = state.get("critic_score", 0.0)

    # 条件1: Critic 明确标记 ready_for_polish → 直接通过
    if ready:
        logger.info(
            f"[WriterAgent] Critic ready_for_polish (score={score:.1f}/10) → polish"
        )
        return _CITE_AND_POLISH

    # 条件2: 评分 >= 8.0 → 质量达标，即使 Critic 标记未 ready 也提前退出
    if score >= 8.0:
        logger.info(
            f"[WriterAgent] score threshold met ({score:.1f}/10 >= 8.0) → polish"
        )
        return _CITE_AND_POLISH

    # 条件3: 评分 >= 6.0 且至少修订过一次 → 合格退出
    if score >= 6.0 and revision >= 1:
        logger.info(
            f"[WriterAgent] qualified exit (score={score:.1f}/10 >= 6.0, "
            f"revision={revision}) → polish"
        )
        return _CITE_AND_POLISH

    # 条件4: 达到最大修订次数 → 安全兜底
    if revision >= max_rev:
        logger.info(
            f"[WriterAgent] max revisions reached ({revision}/{max_rev}, "
            f"score={score:.1f}/10) → polish"
        )
        return _CITE_AND_POLISH

    logger.info(
        f"[WriterAgent] needs revision "
        f"(rev={revision}/{max_rev}, score={score:.1f}/10) → draft"
    )
    return _DRAFT


async def _cite_and_polish(state: OverallState, config: RunnableConfig) -> dict:
    """Finalise: LLM polish + replace short URLs with real URLs + deduplicate sources."""
    configurable = Configuration.from_runnable_config(config)
    reasoning_model = state.get("reasoning_model") or configurable.answer_model
    logger.info(f"[WriterAgent] polishing 准备使用模型={reasoning_model}")

    draft_text = state.get("report_draft", "")

    # Step A — LLM polish pass
    agent = Agent(model_id=reasoning_model)
    agent.set_step_prompt(polish_instructions)

    # 如果配置中注入了 token 回调，则使用流式调用
    emit_token = config.get("configurable", {}).get("_emit_token")
    if emit_token:

        async def on_token(text: str) -> None:
            await emit_token(text, "cite_and_polish")

        raw = await agent.astream_step(
            on_token,
            research_topic=get_research_topic(state["messages"]),
            draft=draft_text,
            summaries="\n---\n\n".join(state["web_search_result"]),
        )
    else:
        raw = await agent.astep(
            research_topic=get_research_topic(state["messages"]),
            draft=draft_text,
            summaries="\n---\n\n".join(state["web_search_result"]),
        )
    polished = Post.extract_pattern(raw, pattern="markdown")

    unique_sources = []
    for source in state.get("sources_gathered", []):
        if source["short_url"] in polished:
            polished = polished.replace(source["short_url"], source["value"])
            unique_sources.append(source)

    logger.info(
        f"[WriterAgent] polished ({len(polished)} chars), "
        f"{len(unique_sources)} sources cited, "
        f"{state.get('revision_count', 0)} revision(s)"
    )
    return {
        "messages": [AIMessage(content=polished)],
        "sources_gathered": unique_sources,
    }


# ═══════════════════════════════════════════════════════════════════════
# Build the sub-graph (with debate loop)
# ═══════════════════════════════════════════════════════════════════════

_builder = StateGraph(OverallState, config_schema=Configuration)

_builder.add_node(_OUTLINE, _outline)
_builder.add_node(_DRAFT, _draft)
_builder.add_node(_CRITIC_REVIEW, _critic_review)
_builder.add_node(_CITE_AND_POLISH, _cite_and_polish)

# Flow: outline → draft → critic → (loop or polish)
_builder.add_edge(START, _OUTLINE)
_builder.add_edge(_OUTLINE, _DRAFT)
_builder.add_edge(_DRAFT, _CRITIC_REVIEW)
_builder.add_conditional_edges(
    _CRITIC_REVIEW,
    _route_after_critic,
    [_DRAFT, _CITE_AND_POLISH],
)
_builder.add_edge(_CITE_AND_POLISH, END)

writer_agent_graph = _builder.compile(name="WriterAgent")

try:
    display(Image(writer_agent_graph.get_graph().draw_mermaid_png(output_file_path="./WriterAgent子图.png")))
except Exception:
    pass