"""
智能问答路由
============
POST /regulation  — 规范条款问答 (RAG，从共享索引)
POST /atlas       — 图集节点图文问答
"""

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.core.registry import get_regulation_qa, get_atlas_qa, get_stats

router = APIRouter()


@router.post("/regulation")
async def chat_regulation(
    body: dict,
    user: dict = Depends(get_current_user),
):
    """规范问答 RAG Pipeline — 从已上传文档的共享索引中检索"""
    question = body.get("question", "")
    chat_history = body.get("chat_history", [])
    filters = body.get("filters")
    top_k = body.get("top_k", 5)

    stats = get_stats()
    if stats["total_chunks"] == 0:
        return {
            "answer": "当前索引为空，请先在「文档管理」页面上传规范文档（PDF/TXT），系统将自动解析并建立检索索引。",
            "sources": [],
            "disclaimer": "AI 回答仅供参考，请以规范原文和纸质图集为准",
        }

    qa = get_regulation_qa()
    return qa.answer(question, chat_history, filters=filters, top_k=top_k)


@router.post("/atlas")
async def chat_atlas(
    body: dict,
    user: dict = Depends(get_current_user),
):
    """图集节点图文问答"""
    question = body.get("question", "")
    qa = get_atlas_qa()
    return qa.answer(question)
