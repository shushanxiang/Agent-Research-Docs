"""
文档 Schema
===========
请求/响应 Pydantic 模型。
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel
from uuid import UUID


# ── 上传 ──
class DocumentUploadResponse(BaseModel):
    document_id: UUID
    filename: str
    version: str
    status: str
    parse_task_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── 列表 ──
class DocumentListItem(BaseModel):
    id: UUID
    filename: str
    doc_type: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[DocumentListItem]


# ── 检索 ──
class SearchRequest(BaseModel):
    query: str
    filters: Optional[dict] = {}
    search_mode: str = "hybrid"
    top_k: int = 10
    page: int = 1
    page_size: int = 20


class SearchResultItem(BaseModel):
    clause_id: Optional[str]
    clause_title: Optional[str]
    content: str
    standard_code: Optional[str]
    standard_title: Optional[str]
    chapter_path: Optional[str]
    page_num: Optional[int]
    status: Optional[str]
    score: float
    highlights: List[str] = []


class SearchResponse(BaseModel):
    total: int
    results: List[SearchResultItem]
