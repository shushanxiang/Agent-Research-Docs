"""
全局配置管理
============
集中管理所有环境变量和应用配置，使用 pydantic-settings 进行校验。
"""

from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- 项目基础 ---
    PROJECT_NAME: str = "建筑智能文档助手"
    VERSION: str = "0.1.0"
    DEBUG: bool = False
    CORS_ORIGINS: List[str] = ["http://localhost:8501", "http://localhost:3000"]

    # --- 数据库 ---
    DATABASE_URL: str = "postgresql+asyncpg://user:XX@localhost:5432/building_docs"
    DATABASE_URL_SYNC: str = "postgresql://user:XX@localhost:5432/building_docs"

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Chroma ---
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000

    # --- 对象存储 (MinIO / OSS) ---
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = XX
    MINIO_SECRET_KEY: str = XX
    MINIO_BUCKET: str = "building-docs"

    # --- MinerU 解析服务 ---
    # 本地 Docker 服务
    MINERU_API_URL: str = "http://localhost:8001"
    # MinerU 云服务 Token (https://mineru.net/apiManage/token)
    MINERU_API_TOKEN: Optional[str] = None
    # 云服务模型版本: pipeline / vlm (推荐) / MinerU-HTML
    MINERU_MODEL_VERSION: str = "vlm"

    # --- BGE-M3 Embedding ---
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-m3"
    EMBEDDING_DEVICE: str = "cuda"  # cuda / cpu

    # --- 通义千问 (DashScope) ---
    DASHSCOPE_API_KEY: Optional[str] = None
    QWEN_MODEL_DEFAULT: str = "qwen-max"
    QWEN_MODEL_LITE: str = "qwen-turbo"

    # --- 安全 ---
    JWT_SECRET: str = XX
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480  # 8 小时

    # --- 审计 ---
    AUDIT_LOG_RETENTION_DAYS: int = 180

    # --- 文件上传 ---
    MAX_UPLOAD_SIZE_MB: int = 200
    ALLOWED_EXTENSIONS: List[str] = [
        "pdf", "jpg", "jpeg", "png", "tiff", "tif",
        "doc", "docx", "xls", "xlsx", "ppt", "pptx",
        "txt", "zip", "rar",
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # 忽略未知环境变量


settings = Settings()
