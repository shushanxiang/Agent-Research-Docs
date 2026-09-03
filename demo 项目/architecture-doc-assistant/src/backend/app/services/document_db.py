"""
文档数据服务 (PostgreSQL)
=========================
基于 SQLAlchemy 异步会话的文档 CRUD 操作。

替代原 core/registry.py 中的内存字典 _documents，
所有文档元数据持久化到 PostgreSQL。
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, Regulation, Clause, AtlasNode, Chapter
from app.models.session import User

logger = logging.getLogger(__name__)


class DocumentDBService:
    """文档元数据 CRUD（PostgreSQL）"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Document ──

    async def create_document(
        self,
        filename: str,
        storage_path: str,
        file_hash: str,
        doc_type: Optional[str] = None,
        file_size: int = 0,
        mime_type: Optional[str] = None,
        uploader_id: Optional[uuid.UUID] = None,
    ) -> Document:
        """创建文档记录"""
        doc = Document(
            filename=filename,
            storage_path=storage_path,
            hash=file_hash,
            doc_type=doc_type,
            file_size=file_size,
            mime_type=mime_type,
            status="processing",
            uploader_id=uploader_id,
        )
        self.db.add(doc)
        await self.db.flush()
        logger.info(f"[DocumentDB] created document: {doc.id} '{filename}'")
        return doc

    async def update_document_status(self, doc_id: uuid.UUID, status: str):
        """更新文档处理状态"""
        doc = await self.db.get(Document, doc_id)
        if doc:
            doc.status = status
            doc.updated_at = datetime.utcnow()
            await self.db.flush()

    async def get_document(self, doc_id: uuid.UUID) -> Optional[Document]:
        return await self.db.get(Document, doc_id)

    async def get_document_by_hash(self, file_hash: str) -> Optional[Document]:
        result = await self.db.execute(
            select(Document).where(Document.hash == file_hash)
        )
        return result.scalar_one_or_none()

    async def list_documents(
        self,
        page: int = 1,
        page_size: int = 20,
        doc_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> dict:
        """分页查询文档列表"""
        query = select(Document)
        count_q = select(func.count(Document.id))

        if doc_type:
            query = query.where(Document.doc_type == doc_type)
            count_q = count_q.where(Document.doc_type == doc_type)
        if status:
            query = query.where(Document.status == status)
            count_q = count_q.where(Document.status == status)

        total_r = await self.db.execute(count_q)
        total = total_r.scalar() or 0

        query = query.order_by(Document.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        items = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": str(d.id),
                    "filename": d.filename,
                    "storage_path": d.storage_path,
                    "doc_type": d.doc_type,
                    "file_size": d.file_size,
                    "status": d.status,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
                for d in items
            ],
        }

    async def delete_document(self, doc_id: uuid.UUID) -> bool:
        """删除文档及关联的规范/条款/图集节点"""
        doc = await self.db.get(Document, doc_id)
        if not doc:
            return False
        await self.db.delete(doc)
        await self.db.flush()
        logger.info(f"[DocumentDB] deleted document: {doc_id}")
        return True

    async def get_stats(self) -> dict:
        """获取文档统计"""
        total_r = await self.db.execute(select(func.count(Document.id)))
        total_docs = total_r.scalar() or 0

        completed_r = await self.db.execute(
            select(func.count(Document.id)).where(Document.status == "completed")
        )
        return {
            "total_documents": total_docs,
            "completed_documents": completed_r.scalar() or 0,
        }

    # ── Regulation ──

    async def create_regulation(
        self,
        document_id: uuid.UUID,
        standard_code: str,
        title: str,
        status: str = "有效",
        issue_date: Optional[datetime] = None,
        effective_date: Optional[datetime] = None,
        publisher: Optional[str] = None,
    ) -> Regulation:
        reg = Regulation(
            document_id=document_id,
            standard_code=standard_code,
            title=title,
            status=status,
            issue_date=issue_date,
            effective_date=effective_date,
            publisher=publisher,
        )
        self.db.add(reg)
        await self.db.flush()
        return reg

    async def get_regulation_by_code(self, standard_code: str) -> Optional[Regulation]:
        result = await self.db.execute(
            select(Regulation).where(Regulation.standard_code == standard_code)
        )
        return result.scalar_one_or_none()

    # ── Clause ──

    async def batch_insert_clauses(
        self, regulation_id: uuid.UUID, chapter_title: str, clauses_data: list
    ) -> list:
        """批量插入条款（从 chunk 列表）"""
        # 创建或复用章节
        chapter = Chapter(
            regulation_id=regulation_id,
            title=chapter_title,
            level=1,
            order_index=0,
        )
        self.db.add(chapter)
        await self.db.flush()

        inserted = []
        for clause_data in clauses_data:
            clause = Clause(
                chapter_id=chapter.id,
                clause_id=clause_data.get("clause_id", ""),
                title=clause_data.get("clause_id", ""),
                content=clause_data.get("content", ""),
                page_num=clause_data.get("metadata", {}).get("page_num", 1),
                references=clause_data.get("references", []),
            )
            self.db.add(clause)
            inserted.append(clause)

        await self.db.flush()
        logger.info(
            f"[DocumentDB] inserted {len(inserted)} clauses "
            f"for regulation {regulation_id}"
        )
        return inserted

    # ── AtlasNode ──

    async def batch_insert_atlas_nodes(
        self, document_id: uuid.UUID, atlas_code: str, nodes_data: list
    ) -> list:
        """批量插入图集节点"""
        inserted = []
        for node_data in nodes_data:
            node = AtlasNode(
                document_id=document_id,
                atlas_code=atlas_code,
                node_id=node_data.get("node_id", ""),
                node_name=node_data.get("node_name", ""),
                description=node_data.get("description", ""),
                materials=node_data.get("materials", []),
                page_num=node_data.get("page_num", 1),
                image_paths=node_data.get("image_paths", []),
            )
            self.db.add(node)
            inserted.append(node)

        await self.db.flush()
        logger.info(
            f"[DocumentDB] inserted {len(inserted)} atlas nodes "
            f"for document {document_id}"
        )
        return inserted
