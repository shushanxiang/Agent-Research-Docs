"""
FastAPI 应用主入口 v2.0
=======================
挂载所有路由、中间件、数据库生命周期事件。

新增 v2.0 模块：
  - 数据库生命周期（PostgreSQL 连接池管理）
  - 服务初始化（ChromaDB / Embedding / MinIO 可用性检测）
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import documents, search, chat, atlas, regulations, admin, enterprise
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.database import init_db, dispose_db
from app.core.registry import initialize_services

# 初始化日志
setup_logging()


# ── 应用生命周期 ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动/关闭回调"""
    # 启动
    try:
        await init_db()
    except Exception as e:
        print(f"[启动] 数据库初始化跳过: {e}")

    try:
        initialize_services()
    except Exception as e:
        print(f"[启动] 服务初始化跳过: {e}")

    yield

    # 关闭
    try:
        await dispose_db()
    except Exception:
        pass


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="建筑行业智能文档助手 - RAG 知识问答平台 (v2.0)",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== 路由注册 =====
app.include_router(documents.router, prefix="/api/v1/documents", tags=["文档管理"])
app.include_router(search.router, prefix="/api/v1/search", tags=["检索服务"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["智能问答"])
app.include_router(atlas.router, prefix="/api/v1/atlas", tags=["图集管理"])
app.include_router(regulations.router, prefix="/api/v1/regulations", tags=["规范管理"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["系统管理"])
app.include_router(enterprise.router, prefix="/api/v1/enterprise", tags=["企业知识库"])

# 静态文件：Markdown 解析结果预览
MD_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "markdown")
os.makedirs(MD_DIR, exist_ok=True)
app.mount("/markdown", StaticFiles(directory=MD_DIR), name="markdown")


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "version": settings.VERSION}


@app.get("/health/full")
async def health_check_full():
    """完整健康检查（含各模块状态）"""
    from app.core.registry import get_stats
    from app.services.embedding import get_embedding_mode
    from app.core.vectordb import is_chroma_available
    from app.services.storage import is_minio_available

    return {
        "status": "ok",
        "version": settings.VERSION,
        "modules": {
            "chromadb": is_chroma_available(),
            "embedding": get_embedding_mode(),
            "minio": is_minio_available(),
        },
        "stats": get_stats(),
    }
