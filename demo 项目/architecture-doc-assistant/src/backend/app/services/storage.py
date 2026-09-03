"""
对象存储服务 (MinIO / S3-compatible)
====================================
管理文档原始文件、解析结果、缩略图的上传/下载/删除。

支持 MinIO 和任意 S3-compatible 存储（阿里云 OSS 等）。
当 MinIO 不可用时自动降级为本地文件系统。
"""

import logging
import os
import uuid
from io import BytesIO
from pathlib import Path
from typing import Optional, BinaryIO, Union

from app.core.config import settings

logger = logging.getLogger(__name__)

# MinIO / S3 客户端（延迟初始化）
_minio_client = None
_minio_available = False


def _get_minio_client():
    """延迟初始化 MinIO 客户端"""
    global _minio_client, _minio_available

    if _minio_client is not None:
        return _minio_client

    try:
        from minio import Minio
        _minio_client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=False,  # 开发环境关闭 TLS
        )
        # 检查连接
        _minio_client.list_buckets()
        _minio_available = True
        logger.info(f"[Storage] MinIO 已连接: {settings.MINIO_ENDPOINT}")
    except Exception as e:
        logger.warning(
            f"[Storage] MinIO 不可用 ({e})，降级为本地文件系统."
            f" MinIO 地址: {settings.MINIO_ENDPOINT}"
        )
        _minio_client = None
        _minio_available = False

    return _minio_client


def is_minio_available() -> bool:
    """检查 MinIO 是否可用"""
    _get_minio_client()
    return _minio_available


def _ensure_bucket(bucket_name: str):
    """确保存储桶存在"""
    client = _get_minio_client()
    if client and not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)
        logger.info(f"[Storage] 创建存储桶: {bucket_name}")


# ── 上传 ──


def upload_file(
    file_data: Union[bytes, BinaryIO, BytesIO],
    filename: str,
    content_type: str = "application/octet-stream",
    prefix: str = "documents",
) -> str:
    """
    上传文件到对象存储，返回存储路径。

    Args:
        file_data: 文件内容（bytes 或 file-like object）
        filename: 原始文件名
        content_type: MIME 类型
        prefix: 存储前缀（如 documents / markdown / thumbnails）

    Returns:
        存储路径，格式: {prefix}/{uuid}_{filename}
    """
    # 生成唯一存储名
    file_id = str(uuid.uuid4())[:12]
    ext = Path(filename).suffix
    object_name = f"{prefix}/{file_id}_{Path(filename).stem}{ext}"

    client = _get_minio_client()

    if client:
        # MinIO 上传
        _ensure_bucket(settings.MINIO_BUCKET)

        if isinstance(file_data, bytes):
            file_data = BytesIO(file_data)

        length = file_data.seek(0, os.SEEK_END) if hasattr(file_data, "seek") else None
        if hasattr(file_data, "seek"):
            file_data.seek(0)

        client.put_object(
            bucket_name=settings.MINIO_BUCKET,
            object_name=object_name,
            data=file_data,
            length=length or -1,
            content_type=content_type,
        )
        logger.info(f"[Storage] MinIO 上传: {object_name}")
    else:
        # 本地降级
        local_dir = os.path.join("data", prefix)
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, f"{file_id}_{filename}")

        if isinstance(file_data, bytes):
            with open(local_path, "wb") as f:
                f.write(file_data)
        else:
            if hasattr(file_data, "seek"):
                file_data.seek(0)
            with open(local_path, "wb") as f:
                f.write(file_data.read())

        logger.info(f"[Storage] 本地存储: {local_path}")

    return object_name


async def upload_file_async(
    content: bytes,
    filename: str,
    content_type: str = "application/octet-stream",
    prefix: str = "documents",
) -> str:
    """异步上传（内部调用同步方法，生产环境可替换为 aiobotocore）"""
    return upload_file(content, filename, content_type, prefix)


# ── 下载 ──


def download_file(object_name: str) -> Optional[bytes]:
    """
    从对象存储下载文件内容。

    Returns:
        文件字节内容，不存在时返回 None
    """
    client = _get_minio_client()

    if client:
        try:
            response = client.get_object(
                bucket_name=settings.MINIO_BUCKET,
                object_name=object_name,
            )
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except Exception as e:
            logger.warning(f"[Storage] MinIO 下载失败: {object_name} ({e})")
            return None
    else:
        local_path = os.path.join("data", object_name)
        if os.path.exists(local_path):
            with open(local_path, "rb") as f:
                return f.read()
        return None


def get_download_url(object_name: str, expires: int = 3600) -> Optional[str]:
    """
    生成预签名下载 URL（MinIO）或文件路径（本地）。

    Args:
        object_name: 存储对象名
        expires: URL 有效期（秒）

    Returns:
        下载链接
    """
    client = _get_minio_client()

    if client:
        try:
            url = client.presigned_get_object(
                bucket_name=settings.MINIO_BUCKET,
                object_name=object_name,
                expires=expires,
            )
            return url
        except Exception as e:
            logger.warning(f"[Storage] 生成预签名 URL 失败: {object_name} ({e})")
            return None
    else:
        # 本地返回相对路径
        local_path = os.path.join("data", object_name)
        if os.path.exists(local_path):
            return f"/{object_name}"
        return None


# ── 删除 ──


def delete_file(object_name: str) -> bool:
    """删除存储文件"""
    client = _get_minio_client()

    if client:
        try:
            client.remove_object(
                bucket_name=settings.MINIO_BUCKET,
                object_name=object_name,
            )
            logger.info(f"[Storage] MinIO 删除: {object_name}")
            return True
        except Exception as e:
            logger.warning(f"[Storage] MinIO 删除失败: {object_name} ({e})")
            return False
    else:
        local_path = os.path.join("data", object_name)
        if os.path.exists(local_path):
            os.remove(local_path)
            logger.info(f"[Storage] 本地删除: {local_path}")
            return True
        return False


def delete_prefix(prefix: str) -> int:
    """批量删除指定前缀下的所有文件，返回删除数量"""
    client = _get_minio_client()
    deleted = 0

    if client:
        objects = client.list_objects(
            bucket_name=settings.MINIO_BUCKET,
            prefix=prefix,
            recursive=True,
        )
        for obj in objects:
            try:
                client.remove_object(settings.MINIO_BUCKET, obj.object_name)
                deleted += 1
            except Exception:
                pass
    else:
        local_dir = os.path.join("data", prefix)
        if os.path.isdir(local_dir):
            for root, _, files in os.walk(local_dir):
                for f in files:
                    os.remove(os.path.join(root, f))
                    deleted += 1

    logger.info(f"[Storage] 批量删除 {prefix}: {deleted} 个文件")
    return deleted
