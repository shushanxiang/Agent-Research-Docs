"""
文档模型
========
核心实体：Document, Regulation, Chapter, Clause, AtlasNode, Image
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, BigInteger, Text, Float,
    DateTime, ForeignKey, CheckConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.types import UUIDType, JSONType


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    filename = Column(String(500), nullable=False)
    storage_path = Column(String(1000), nullable=False)
    doc_type = Column(String(50))
    file_size = Column(BigInteger)
    mime_type = Column(String(100))
    hash = Column(String(64), unique=True)
    status = Column(String(20), default="processing")
    project_id = Column(UUIDType, nullable=True)
    uploader_id = Column(UUIDType, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "doc_type IN ('规范','图集','变更单','图纸','报告','施工日志')",
            name="ck_doc_type",
        ),
    )


class Regulation(Base):
    __tablename__ = "regulations"

    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    document_id = Column(UUIDType, ForeignKey("documents.id"))
    standard_code = Column(String(100))
    title = Column(String(500))
    issue_date = Column(DateTime)
    effective_date = Column(DateTime)
    abolish_date = Column(DateTime, nullable=True)
    status = Column(String(20))
    publisher = Column(String(200))
    vector_collection = Column(String(100))

    chapters = relationship("Chapter", back_populates="regulation")


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    regulation_id = Column(UUIDType, ForeignKey("regulations.id"))
    parent_id = Column(UUIDType, ForeignKey("chapters.id"), nullable=True)
    title = Column(String(500))
    level = Column(Integer)
    order_index = Column(Integer)
    page_start = Column(Integer)
    page_end = Column(Integer)
    vector_id = Column(String(200))

    regulation = relationship("Regulation", back_populates="chapters")
    clauses = relationship("Clause", back_populates="chapter")


class Clause(Base):
    __tablename__ = "clauses"

    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    chapter_id = Column(UUIDType, ForeignKey("chapters.id"))
    clause_id = Column(String(100))
    title = Column(String(500))
    content = Column(Text)
    page_num = Column(Integer)
    vector_id = Column(String(200))
    references = Column(JSONType, default=list)

    chapter = relationship("Chapter", back_populates="clauses")


class AtlasNode(Base):
    __tablename__ = "atlas_nodes"

    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    document_id = Column(UUIDType, ForeignKey("documents.id"))
    atlas_code = Column(String(100))
    node_id = Column(String(100))
    node_name = Column(String(500))
    description = Column(Text)
    materials = Column(JSONType, default=list)
    page_num = Column(Integer)
    image_paths = Column(JSONType, default=list)
    vector_id = Column(String(200))


class Image(Base):
    __tablename__ = "images"

    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    document_id = Column(UUIDType, ForeignKey("documents.id"))
    node_id = Column(UUIDType, ForeignKey("atlas_nodes.id"), nullable=True)
    page_num = Column(Integer)
    storage_path = Column(String(1000))
    thumbnail_path = Column(String(1000))
    ocr_text = Column(Text)
    bbox = Column(JSONType)
    dpi = Column(Integer)
    clarity_score = Column(Float)
