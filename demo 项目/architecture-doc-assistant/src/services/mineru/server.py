"""
MinerU 解析服务 — HTTP API 入口
================================
启动方式: docker compose up mineru  或  python server.py

API:
  POST /parse          — 提交 PDF 解析任务（异步）
  GET  /parse/{task_id} — 查询解析进度
  GET  /health         — 健康检查
"""

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mineru")

app = FastAPI(title="MinerU Parser Service", version="1.0.0")

# ── 任务状态存储（生产环境替换为 Redis DB）──
_tasks: dict = {}

TEMP_DIR = Path(os.getenv("MINERU_TEMP_DIR", "/app/temp"))
TEMP_DIR.mkdir(parents=True, exist_ok=True)


class ParseRequest(BaseModel):
    file_path: str              # 对象存储路径或本地路径
    output_format: str = "json" # json / markdown
    doc_type: Optional[str] = None  # 规范 / 图集 / 图纸 ...


class ParseStatus(BaseModel):
    task_id: str
    status: str                 # pending / processing / completed / failed
    progress: int = 0           # 0-100
    stage: str = ""             # 当前阶段名称
    result: Optional[dict] = None
    error: Optional[str] = None


@app.on_event("startup")
async def startup():
    """验证 MinerU 核心库是否正常加载"""
    try:
        import magic_pdf
        logger.info(f"MinerU (magic-pdf) loaded successfully, version: {magic_pdf.__version__}")
    except ImportError:
        logger.warning("magic-pdf not installed — MinerU parsing will be unavailable")


@app.get("/health")
async def health():
    """健康检查 + 依赖检测"""
    checks = {}
    # magic-pdf
    try:
        import magic_pdf
        checks["magic_pdf"] = f"OK ({magic_pdf.__version__})"
    except ImportError:
        checks["magic_pdf"] = "NOT INSTALLED"
    # torch
    try:
        import torch
        checks["torch"] = f"OK ({torch.__version__}, cuda={torch.cuda.is_available()})"
    except ImportError:
        checks["torch"] = "NOT INSTALLED"
    # PIL
    try:
        import PIL
        checks["pillow"] = f"OK ({PIL.__version__})"
    except ImportError:
        checks["pillow"] = "NOT INSTALLED"
    # MinerU Cloud
    token = os.getenv("MINERU_API_TOKEN", "")
    checks["mineru_cloud"] = "OK (token set)" if token else "NOT CONFIGURED"

    all_ok = all(v.startswith("OK") for v in checks.values())
    return {
        "status": "healthy" if all_ok else "degraded",
        "dependencies": checks,
    }


@app.post("/parse", response_model=ParseStatus)
async def parse_document(req: ParseRequest):
    """
    提交文档解析任务
    
    file_path: 本地路径（Docker 挂载卷）或对象存储 URL
    返回 task_id，通过 GET /parse/{task_id} 轮询进度
    """
    task_id = str(uuid.uuid4())[:8]
    _tasks[task_id] = ParseStatus(task_id=task_id, status="pending")

    # 异步执行解析（简化版，生产环境用 Celery）
    import asyncio
    asyncio.create_task(_run_parse(task_id, req.file_path, req.output_format))

    return _tasks[task_id]


@app.get("/parse/{task_id}", response_model=ParseStatus)
async def get_parse_status(task_id: str):
    """查询解析任务进度"""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="task not found")
    return _tasks[task_id]


async def _run_parse(task_id: str, file_path: str, output_format: str):
    """
    实际执行 MinerU 解析
    
    流程:
      1. 校验文件存在
      2. 版面分析 (layout detection)
      3. 文字提取 + OCR
      4. 表格/图片识别
      5. 输出 JSON/Markdown
    """
    task = _tasks[task_id]
    task.status = "processing"

    try:
        # Stage 1: 文件校验
        task.stage = "文件校验"
        task.progress = 10
        local_path = Path(file_path)
        if not local_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # Stage 2: MinerU 解析
        task.stage = "版面分析 + 结构化解析"
        task.progress = 30

        import magic_pdf
        from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
        from magic_pdf.data.dataset import PymuDocDataset
        from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze

        # 读取 PDF
        task.stage = "PDF 读取"
        task.progress = 40
        reader = FileBasedDataReader("")
        pdf_bytes = local_path.read_bytes()
        ds = PymuDocDataset(pdf_bytes)

        # 版面分析
        task.stage = "版面分析"
        task.progress = 60
        if ds.classify() == "ocr":
            task.stage = "OCR 识别（扫描版）"
            infer_result = ds.apply(doc_analyze, ocr=True)
            pipe_result = infer_result.pipe_ocr_mode(
                FileBasedDataWriter(str(TEMP_DIR / f"{task_id}_images"))
            )
        else:
            infer_result = ds.apply(doc_analyze, ocr=False)
            pipe_result = infer_result.pipe_txt_mode(
                FileBasedDataWriter(str(TEMP_DIR / f"{task_id}_images")),
                f"{task_id}.md",
            )

        # Stage 3: 结果组装
        task.stage = "结果生成"
        task.progress = 90

        result = {
            "markdown_file": str(TEMP_DIR / f"{task_id}.md"),
            "images_dir": str(TEMP_DIR / f"{task_id}_images"),
            "content_length": 0,
        }

        # 读取 markdown 结果
        md_path = TEMP_DIR / f"{task_id}.md"
        if md_path.exists():
            result["content_length"] = len(md_path.read_text(encoding="utf-8"))

        task.result = result
        task.progress = 100
        task.status = "completed"
        logger.info(f"[MinerU] task {task_id} completed, content_length={result['content_length']}")

    except ImportError:
        # magic-pdf 未安装时的模拟输出
        task.stage = "模拟解析（magic-pdf 未安装）"
        task.progress = 100
        task.result = {
            "mock": True,
            "note": "magic-pdf not installed — returning mock structure for API testing",
            "chapters": [
                {"title": "第1章 总则", "level": 1, "clauses": [
                    {"clause_id": "1.0.1", "content": "为使建筑防火设计做到安全适用..."}
                ]}
            ],
            "images": [],
            "tables": [],
        }
        task.status = "completed"
        logger.warning(f"[MinerU] task {task_id} mock-completed (magic-pdf not installed)")

    except Exception as e:
        task.status = "failed"
        task.error = str(e)
        logger.error(f"[MinerU] task {task_id} failed: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
