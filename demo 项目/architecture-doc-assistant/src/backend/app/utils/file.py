"""
工具函数
========
文件处理、哈希计算、格式校验等公共工具。
"""

import hashlib
from pathlib import Path


def compute_file_hash(file_path: str | Path, algorithm: str = "sha256") -> str:
    """计算文件哈希"""
    h = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_bytes_hash(data: bytes, algorithm: str = "sha256") -> str:
    """计算字节数据的哈希"""
    return hashlib.new(algorithm, data).hexdigest()


def get_file_extension(filename: str) -> str:
    """获取文件扩展名（小写）"""
    return Path(filename).suffix.lower().lstrip(".")


def is_allowed_extension(filename: str, allowed: set[str]) -> bool:
    """检查文件扩展名是否在允许列表中"""
    return get_file_extension(filename) in allowed
