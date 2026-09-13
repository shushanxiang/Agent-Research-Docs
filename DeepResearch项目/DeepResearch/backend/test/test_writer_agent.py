"""Integration tests for WriterAgent sub-graph — nodes, routing, and debate loop."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.state import OverallState
from agent.sub_agents.writer_agent import (
    writer_agent_graph,
    _outline,
    _draft,
    _critic_review,
    _route_after_critic,
    _cite_and_polish,
    _OUTLINE,
    _DRAFT,
    _CRITIC_REVIEW,
    _CITE_AND_POLISH,
)


# ═══════════════════════════════════════════════════════════════════════
# Graph topology
# ═══════════════════════════════════════════════════════════════════════

class TestWriterAgentGraphTopology:
    def test_graph_is_compiled(self):
        assert writer_agent_graph is not None
        assert hasattr(writer_agent_graph, "nodes")

    def test_required_nodes_exist(self):
        nodes = list(writer_agent_graph.nodes.keys())
        assert _OUTLINE in nodes
        assert _DRAFT in nodes
        assert _CRITIC_REVIEW in nodes
        assert _CITE_AND_POLISH in nodes


# ═══════════════════════════════════════════════════════════════════════
# _outline node (async)
# ═══════════════════════════════════════════════════════════════════════

class TestOutline:
    @pytest.mark.asyncio
    async def test_generates_outline(self, sample_state):
        with patch("agent.sub_agents.writer_agent.Agent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_agent.astep = AsyncMock(
                return_value="```markdown\n# 报告大纲\n\n## 第一章\n## 第二章\n```"
            )
            mock_agent_cls.return_value = mock_agent

            result = await _outline(sample_state, {"configurable": {}})

            assert "report_outline" in result
            assert "第一章" in result["report_outline"]
            assert result["revision_count"] == 0
            assert result["max_revisions"] == 3


# ═══════════════════════════════════════════════════════════════════════
# _draft node (async)
# ═══════════════════════════════════════════════════════════════════════

class TestDraft:
    @pytest.mark.asyncio
    async def test_first_draft_from_scratch(self, sample_state):
        with patch("agent.sub_agents.writer_agent.Agent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_agent.astep = AsyncMock(
                return_value="```markdown\n# 报告正文\n\n这是草稿内容\n```"
            )
            mock_agent_cls.return_value = mock_agent

            result = await _draft(sample_state, {"configurable": {}})

            assert "report_draft" in result
            assert "报告正文" in result["report_draft"]
            assert result.get("revision_count", 0) == 0

    @pytest.mark.asyncio
    async def test_revision_with_feedback(self, sample_state):
        state = {
            **sample_state,
            "critic_feedback": "## 审稿评分: 5/10\n## 具体问题:\n- 数据源需要更新",
            "report_outline": "# Outline\nTest",
            "revision_count": 1,
        }

        with patch("agent.sub_agents.writer_agent.Agent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_agent.astep = AsyncMock(
                return_value="```markdown\n# 修订后的报告\n\n已修改\n```"
            )
            mock_agent_cls.return_value = mock_agent

            result = await _draft(state, {"configurable": {}})

            assert "report_draft" in result
            assert result["revision_count"] == 2
            assert result["critic_feedback"] == ""


# ═══════════════════════════════════════════════════════════════════════
# _critic_review node (async)
# ═══════════════════════════════════════════════════════════════════════

class TestCriticReview:
    @pytest.mark.asyncio
    async def test_review_with_issues(self, sample_state):
        from agent.tools_and_schemas import CritiqueResult, Issue

        state = {
            **sample_state,
            "report_draft": "# Draft content\n\nSome analysis here.",
        }

        with patch("agent.sub_agents.writer_agent.JsonAgent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_agent.astep = AsyncMock(return_value=CritiqueResult(
                overall_rating=6.5,
                issues=[
                    Issue(
                        severity="critical",
                        location="第1章",
                        problem="数据源链接失效",
                        suggestion="更新为最新链接",
                    ),
                    Issue(
                        severity="minor",
                        location="第3章",
                        problem="措辞不够专业",
                        suggestion="使用更正式的表述",
                    ),
                ],
                ready_for_polish=False,
                summary="需要小修",
            ))
            mock_agent_cls.return_value = mock_agent

            result = await _critic_review(state, {"configurable": {}})

            assert result["critic_score"] == 6.5
            assert result["ready_for_polish"] is False
            assert "critic_feedback" in result
            assert "审稿评分: 6.5/10" in result["critic_feedback"]
            assert "CRITICAL" in result["critic_feedback"]
            assert "MINOR" in result["critic_feedback"]

    @pytest.mark.asyncio
    async def test_review_no_issues(self, sample_state):
        from agent.tools_and_schemas import CritiqueResult

        state = {**sample_state, "report_draft": "# Perfect draft"}

        with patch("agent.sub_agents.writer_agent.JsonAgent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_agent.astep = AsyncMock(return_value=CritiqueResult(
                overall_rating=9.0,
                issues=[],
                ready_for_polish=True,
                summary="优秀，可直接发布",
            ))
            mock_agent_cls.return_value = mock_agent

            result = await _critic_review(state, {"configurable": {}})

            assert result["critic_score"] == 9.0
            assert result["ready_for_polish"] is True
            assert "无明显问题" in result["critic_feedback"]


# ═══════════════════════════════════════════════════════════════════════
# _route_after_critic routing (sync — pure routing)
# ═══════════════════════════════════════════════════════════════════════

class TestRouteAfterCritic:
    def test_ready_for_polish_true_goes_to_polish(self, sample_state):
        """条件1: ready_for_polish=True — 无论分数高低都进入润色."""
        state = {
            **sample_state,
            "ready_for_polish": True,
            "revision_count": 0,
            "max_revisions": 3,
            "critic_score": 4.0,
        }
        result = _route_after_critic(state, {"configurable": {}})
        assert result == _CITE_AND_POLISH

    def test_score_gte_8_triggers_polish(self, sample_state):
        """条件2: 评分 >= 8.0 — 即使 ready_for_polish=False 也提前进入润色."""
        state = {
            **sample_state,
            "ready_for_polish": False,
            "revision_count": 0,
            "max_revisions": 3,
            "critic_score": 8.5,
        }
        result = _route_after_critic(state, {"configurable": {}})
        assert result == _CITE_AND_POLISH

    def test_score_8_exact_triggers_polish(self, sample_state):
        """条件2 边界: 评分 == 8.0 也触发润色."""
        state = {
            **sample_state,
            "ready_for_polish": False,
            "revision_count": 0,
            "max_revisions": 3,
            "critic_score": 8.0,
        }
        result = _route_after_critic(state, {"configurable": {}})
        assert result == _CITE_AND_POLISH

    def test_score_gte_6_with_revision_triggers_polish(self, sample_state):
        """条件3: 评分 >= 6.0 且至少修订过 1 次 — 合格退出."""
        state = {
            **sample_state,
            "ready_for_polish": False,
            "revision_count": 1,
            "max_revisions": 3,
            "critic_score": 6.5,
        }
        result = _route_after_critic(state, {"configurable": {}})
        assert result == _CITE_AND_POLISH

    def test_score_6_exact_with_revision_triggers_polish(self, sample_state):
        """条件3 边界: 评分 == 6.0 + revision=1 — 触发合格退出."""
        state = {
            **sample_state,
            "ready_for_polish": False,
            "revision_count": 1,
            "max_revisions": 3,
            "critic_score": 6.0,
        }
        result = _route_after_critic(state, {"configurable": {}})
        assert result == _CITE_AND_POLISH

    def test_score_gte_6_first_pass_stays_in_draft(self, sample_state):
        """评分 >= 6.0 但首次 draft（revision=0）— 不满足条件3，继续修订."""
        state = {
            **sample_state,
            "ready_for_polish": False,
            "revision_count": 0,
            "max_revisions": 3,
            "critic_score": 7.0,
        }
        result = _route_after_critic(state, {"configurable": {}})
        assert result == _DRAFT

    def test_low_score_with_revision_stays_in_draft(self, sample_state):
        """评分 < 6.0 即使修订过也继续 draft."""
        state = {
            **sample_state,
            "ready_for_polish": False,
            "revision_count": 2,
            "max_revisions": 3,
            "critic_score": 4.5,
        }
        result = _route_after_critic(state, {"configurable": {}})
        assert result == _DRAFT

    def test_max_revisions_force_polish(self, sample_state):
        """条件4: 达到 max_revisions — 安全兜底，即使分数极低也强制进入润色."""
        state = {
            **sample_state,
            "ready_for_polish": False,
            "revision_count": 3,
            "max_revisions": 3,
            "critic_score": 2.0,
        }
        result = _route_after_critic(state, {"configurable": {}})
        assert result == _CITE_AND_POLISH

    def test_first_pass_low_score_goes_to_draft(self, sample_state):
        """首次 draft，低分且 ready_for_polish=False — 回到 draft."""
        state = {
            **sample_state,
            "ready_for_polish": False,
            "revision_count": 0,
            "max_revisions": 3,
            "critic_score": 5.0,
        }
        result = _route_after_critic(state, {"configurable": {}})
        assert result == _DRAFT


# ═══════════════════════════════════════════════════════════════════════
# _cite_and_polish node (async)
# ═══════════════════════════════════════════════════════════════════════

class TestCiteAndPolish:
    @pytest.mark.asyncio
    async def test_polish_and_replace_urls(self, sample_state):
        state = {
            **sample_state,
            "report_draft": "# Report\n\nSee [source](https://search.com/id/0-0) for details.",
        }

        with patch("agent.sub_agents.writer_agent.Agent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_agent.astep = AsyncMock(
                return_value="```markdown\n# Report\n\nSee [source](https://search.com/id/0-0) for details.\n```"
            )
            mock_agent_cls.return_value = mock_agent

            result = await _cite_and_polish(state, {"configurable": {}})

            assert "messages" in result
            final_content = result["messages"][0].content
            assert "https://real.com/1" in final_content
            assert "https://search.com/id/0-0" not in final_content

    @pytest.mark.asyncio
    async def test_polish_deduplicates_sources(self, sample_state):
        draft_with_one_citation = "# Report\n\nSee [ref](https://search.com/id/0-0)."

        state = {
            **sample_state,
            "report_draft": draft_with_one_citation,
        }

        with patch("agent.sub_agents.writer_agent.Agent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_agent.astep = AsyncMock(
                return_value="```markdown\n" + draft_with_one_citation + "\n```"
            )
            mock_agent_cls.return_value = mock_agent

            result = await _cite_and_polish(state, {"configurable": {}})

            assert len(result["sources_gathered"]) == 1
            assert result["sources_gathered"][0]["short_url"] == "https://search.com/id/0-0"
