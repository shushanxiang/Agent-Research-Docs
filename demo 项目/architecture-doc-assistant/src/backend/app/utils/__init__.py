"""
工具函数层
==========
file  — 文件哈希、扩展名校验
llm   — DashScope 通义千问调用封装 + 降级回退
chunking — 文本切块（RAG chunking）
"""

from app.utils.file import compute_file_hash, compute_bytes_hash, get_file_extension, is_allowed_extension
from app.utils.llm import call_qwen, call_qwen_json, is_llm_available, extract_metadata_by_llm
from app.utils.chunking import chunk_clauses

__all__ = [
    "compute_file_hash", "compute_bytes_hash", "get_file_extension", "is_allowed_extension",
    "call_qwen", "call_qwen_json", "is_llm_available", "extract_metadata_by_llm",
    "chunk_clauses",
]
