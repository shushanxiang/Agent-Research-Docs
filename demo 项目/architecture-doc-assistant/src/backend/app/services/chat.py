"""
智能问答服务
============
RegulationQAService — 规范条款 RAG 问答
AtlasQAService    — 图集节点图文问答

完整流程: 检索 → 版本校验 → 上下文组装 → LLM 生成 → 溯源标注
LLM 不可用时自动降级为拼接检索结果。

参见 技术开发文档 §4.3.1—§4.3.2
"""

import json
import logging
from typing import Optional

from app.utils.llm import call_qwen, is_llm_available
from app.retrievers.hybrid import HybridRetriever

logger = logging.getLogger(__name__)

DISCLAIMER = "AI 回答仅供参考，请以规范原文和纸质图集为准"


class RegulationQAService:
    """
    规范条款问答 RAG Pipeline

    流程：检索召回 → 版本校验（废止检测） → Prompt 组装 → LLM 生成 → 溯源标注
    """

    def __init__(self, retriever: Optional[HybridRetriever] = None):
        self.retriever = retriever or HybridRetriever()

    def answer(
        self,
        question: str,
        chat_history: Optional[list] = None,
        filters: Optional[dict] = None,
        top_k: int = 5,
    ) -> dict:
        """
        规范问答 RAG Pipeline

        Args:
            question: 用户自然语言提问
            chat_history: 历史对话 [{"role":"user","content":"..."}, ...]
            filters: 检索过滤条件（如 status、standard_code）
            top_k: 召回条款数量

        Returns:
            {"answer": str, "sources": [...], "disclaimer": str}
        """
        logger.info(f"[RegulationQA] question='{question[:60]}...'")

        # 1. 检索召回
        retrieved = self.retriever.retrieve(
            query=question, filters=filters, top_k=top_k,
        )

        if not retrieved:
            return {
                "answer": "未找到相关规范条款，请尝试更换关键词查询。",
                "sources": [],
                "disclaimer": DISCLAIMER,
            }

        # 2. 版本校验
        validated = self._validate_status(retrieved)

        # 3. 组装上下文
        context = self._build_context(validated)

        # 4. LLM 生成 / 降级
        if is_llm_available():
            answer_text = self._llm_generate(question, context, chat_history)
        else:
            answer_text = self._fallback_answer(question, validated)

        # 5. 溯源
        sources = self._build_sources(validated)

        return {
            "answer": answer_text,
            "sources": sources,
            "disclaimer": DISCLAIMER,
        }

    def _validate_status(self, retrieved: list) -> list:
        """检测已废止条款并标注"""
        validated = []
        for score, chunk in retrieved:
            meta = chunk.get("metadata", {})
            if meta.get("status") == "废止":
                chunk["metadata"]["is_abolished"] = True
                chunk["metadata"]["abolition_warning"] = "该条款已废止"
            validated.append((score, chunk))
        return validated

    @staticmethod
    def _build_context(retrieved: list) -> str:
        """将检索结果组装为 LLM 上下文"""
        parts = []
        for score, chunk in retrieved:
            meta = chunk.get("metadata", {})
            status_tag = ""
            if meta.get("is_abolished"):
                status_tag = "【已废止】"
            parts.append(
                f"条款编号: {meta.get('clause_id','')}  {status_tag}\n"
                f"所属章节: {meta.get('chapter','')}\n"
                f"来源: 《{meta.get('standard_title','')}》{meta.get('standard_code','')}\n"
                f"原文: {chunk.get('content','')}\n"
            )
        return "\n---\n".join(parts)

    @staticmethod
    def _llm_generate(question: str, context: str, chat_history: Optional[list] = None) -> str:
        """调用通义千问生成回答"""
        history_text = ""
        if chat_history:
            history_text = "\n".join(
                f"{m['role']}: {m['content']}" for m in chat_history[-4:]
            )

        prompt = f"""你是一位建筑行业规范专家。请基于以下规范条款内容，回答用户问题。

【回答要求】
1. 直接给出明确结论，不要绕弯子
2. 引用具体规范名称和条款编号（如"依据《建筑防火通用规范》GB 55037-2022 第6.2.3条"）
3. 如果涉及计算，给出公式和计算过程
4. 如果召回的条款已废止，必须在回答开头显著标注"【已废止】"，并说明现行替代条款
5. 如果多个规范对同一问题有不同规定，列出各规范要求并标注差异

【规范条款内容】
{context}

【用户问题】
{question}

【对话历史】
{history_text or '（无历史）'}

请用中文回答："""

        answer = call_qwen(
            [{"role": "user", "content": prompt}],
            model="qwen-max",
            temperature=0.2,
            max_tokens=2048,
        )
        return answer if answer else "通义千问服务暂时不可用，请稍后重试。"

    @staticmethod
    def _fallback_answer(question: str, retrieved: list) -> str:
        """LLM 不可用时的降级回答（拼接检索结果）"""
        parts = ["（未调用 LLM，以下为相关条款原文汇总）\n"]
        for score, chunk in retrieved:
            meta = chunk.get("metadata", {})
            status_tag = "【已废止】" if meta.get("is_abolished") else ""
            parts.append(
                f"■ 《{meta.get('standard_title','')}》"
                f"{meta.get('standard_code','')} "
                f"第{meta.get('clause_id','')}条 {status_tag}\n"
                f"  {chunk.get('content','')}\n"
            )
        return "\n".join(parts)

    @staticmethod
    def _build_sources(retrieved: list) -> list:
        """构建溯源信息"""
        return [
            {
                "clause_id": c[1].get("metadata", {}).get("clause_id", ""),
                "standard_code": c[1].get("metadata", {}).get("standard_code", ""),
                "standard_title": c[1].get("metadata", {}).get("standard_title", ""),
                "chapter": c[1].get("metadata", {}).get("chapter", ""),
                "content": c[1].get("content", ""),
                "is_abolished": c[1].get("metadata", {}).get("is_abolished", False),
                "score": round(c[0], 4),
            }
            for c in retrieved
        ]


class AtlasQAService:
    """
    图集节点问答（图文）

    流程：多模态检索 → 图文组装 → LLM 生成 → 图片关联
    """

    def answer(self, question: str, top_k: int = 3) -> dict:
        """
        图集节点图文问答

        当前为模拟实现（依赖 Chroma 多模态数据就绪后完善）。
        """
        logger.info(f"[AtlasQA] question='{question[:60]}...'")

        if not is_llm_available():
            return {
                "answer": "（未调用 LLM）图集问答模块需要 Chroma 多模态索引就绪后使用。",
                "nodes": [],
                "disclaimer": DISCLAIMER,
            }

        prompt = f"""你是一位建筑施工技术专家。用户询问关于施工做法的问题，
但目前系统中该图集的节点数据尚未入库。请告知用户需要先上传相关图集 PDF 进行解析。

用户问题: {question}

请用中文给出友好提示："""

        answer = call_qwen(
            [{"role": "user", "content": prompt}],
            model="qwen-max",
            temperature=0.2,
            max_tokens=512,
        )

        return {
            "answer": answer or "图集问答功能就绪，请先上传图集文档。",
            "nodes": [],
            "disclaimer": DISCLAIMER,
        }

    def answer_with_nodes(self, question: str, nodes: list) -> dict:
        """
        传入图集节点数据进行问答（端到端测试用）。
        """
        nodes_text = ""
        for n in nodes:
            nodes_text += (
                f"节点编号: {n.get('node_id','')}  {n.get('node_name','')}\n"
                f"所属图集: 《{n.get('atlas_title','')}》{n.get('atlas_code','')}\n"
                f"做法描述:\n{n.get('description','')}\n"
                f"主要材料: {', '.join(n.get('materials',[]))}\n---\n"
            )

        prompt = f"""你是一位建筑施工技术专家。请基于以下图集节点信息，回答用户问题。

【回答要求】
1. 描述具体做法步骤，包括材料、厚度、工序等关键参数
2. 每个节点需标注图集名称和节点编号
3. 如果涉及多个图集做法，对比说明差异（用表格形式）
4. 对关键参数（如厚度、材料）加粗标注

【图集节点信息】
{nodes_text}

【用户问题】
{question}

请用中文回答，保持专业准确："""

        answer = call_qwen(
            [{"role": "user", "content": prompt}],
            model="qwen-max",
            temperature=0.2,
            max_tokens=2048,
        )

        return {
            "answer": answer or "生成回答失败，请稍后重试。",
            "nodes": nodes,
            "disclaimer": DISCLAIMER,
        }
