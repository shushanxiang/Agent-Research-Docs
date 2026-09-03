"""
问答 Schema
===========
ChatRequest / QAResponse / AtlasQAResponse
"""

from typing import List, Optional

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # user / assistant
    content: str


class RegulationChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    chat_history: List[ChatMessage] = []
    filters: Optional[dict] = {}


class SourceItem(BaseModel):
    clause_id: str
    standard_code: str
    standard_title: str
    chapter_path: Optional[str]
    content: str
    page_num: Optional[int]
    status: str
    is_abolished: bool = False


class QAResponse(BaseModel):
    session_id: str
    answer: str
    sources: List[SourceItem]
    related_clauses: List[dict] = []
    abolition_warning: Optional[str] = None
    disclaimer: str = "AI 回答仅供参考，请以规范原文和纸质图集为准"
    confidence: float = 0.0


class AtlasImageItem(BaseModel):
    image_id: str
    thumbnail_url: str
    original_url: str
    page_num: int


class AtlasNodeResult(BaseModel):
    node_id: str
    node_name: str
    atlas_code: str
    atlas_title: Optional[str]
    description: str
    materials: List[str] = []
    images: List[AtlasImageItem] = []
    page_num: int


class AtlasQAResponse(BaseModel):
    session_id: str
    answer: str
    nodes: List[AtlasNodeResult]
    comparison: Optional[dict] = None
    disclaimer: str = "AI 回答仅供参考，请以规范原文和纸质图集为准"
