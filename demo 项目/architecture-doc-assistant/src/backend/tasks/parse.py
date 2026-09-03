"""
文档解析异步任务
================
Celery Task: 文档解析、索引构建、OCR。
参见 技术开发文档 §4.1.2
"""

import logging

from celery import Celery

from app.core.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "architecture_doc_assistant",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
)


@celery_app.task(bind=True, max_retries=3)
def parse_document_task(self, document_id: str):
    """
    异步文档解析任务
    
    流程:
      1. 从对象存储下载文件到本地
      2. 调用 MinerU 解析
      3. 提取元数据
      4. 按文档类型存储结构化数据
      5. 触发索引构建
      6. WebSocket 推送进度
    """
    logger.info(f"[Task] parse_document_task started for {document_id}")
    # TODO: 实现完整解析链路
    return {"document_id": document_id, "status": "completed"}


@celery_app.task(bind=True, max_retries=3)
def build_index_task(self, document_id: str):
    """异步构建向量索引任务"""
    logger.info(f"[Task] build_index_task started for {document_id}")
    # TODO: 文本切片 → BGE-M3 向量化 → Chroma 存储
    return {"document_id": document_id, "status": "indexed"}


@celery_app.task(bind=True, max_retries=2)
def ocr_task(self, image_id: str):
    """异步 OCR 识别任务（扫描版图集）"""
    logger.info(f"[Task] ocr_task started for image {image_id}")
    # TODO: 调用 OCR 服务
    return {"image_id": image_id, "status": "ocr_done"}
