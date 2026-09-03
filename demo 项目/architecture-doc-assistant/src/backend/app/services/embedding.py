"""
BGE-M3 Embedding 服务
=====================
使用 BAAI/bge-m3 模型进行文本向量化。

BGE-M3 特性：
- Dense Vector (1024d): 语义相似度检索
- Sparse Vector: 关键词精确匹配（Lexical Retrieval）
- Multi-Vector (ColBERT): 细粒度交互（用于 Rerank）
- 支持 8192 token 输入长度
- 中英混合效果好

当 GPU/模型不可用时自动降级为 DashScope 云端 Embedding。
"""

import logging
from typing import List, Optional, Tuple

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── 模型实例（延迟加载）──
_embedding_model = None
_embedding_mode = "unavailable"  # "local" | "dashscope" | "unavailable"


def _resolve_device() -> str:
    """
    解析 Embedding 推理设备。

    逻辑：
      1. 配置为 cuda 时，先检测 torch.cuda.is_available()
      2. CUDA 不可用自动回退 cpu，避免运行时崩溃
    """
    if settings.EMBEDDING_DEVICE == "cuda":
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            logger.warning(
                "[Embedding] 配置为 cuda 但 CUDA 不可用，自动回退 cpu"
            )
        except ImportError:
            logger.warning("[Embedding] torch 未安装，自动回退 cpu")
    return "cpu"


def _load_local_model():
    """延迟加载本地 BGE-M3 模型（GPU/CPU）"""
    global _embedding_model, _embedding_mode

    if _embedding_model is not None:
        return _embedding_model

    try:
        from sentence_transformers import SentenceTransformer

        device = _resolve_device()
        logger.info(
            f"[Embedding] 加载本地模型: {settings.EMBEDDING_MODEL_NAME} "
            f"(device={device})"
        )
        _embedding_model = SentenceTransformer(
            settings.EMBEDDING_MODEL_NAME,
            device=device,
            trust_remote_code=True,
        )
        # 预热
        _ = _embedding_model.encode("预热", normalize_embeddings=True)
        _embedding_mode = "local"
        logger.info(
            f"[Embedding] 本地模型就绪, dim={_embedding_model.get_embedding_dimension()}"
        )
    except Exception as e:
        logger.warning(f"[Embedding] 本地模型加载失败: {e}")
        _embedding_model = None

    return _embedding_model


def _get_dashscope_embedding(texts: List[str]) -> Optional[np.ndarray]:
    """通过 DashScope 云端 API 获取 Embedding"""
    try:
        import dashscope
        from dashscope import TextEmbedding

        if not settings.DASHSCOPE_API_KEY:
            return None

        dashscope.api_key = settings.DASHSCOPE_API_KEY

        resp = TextEmbedding.call(
            model="text-embedding-v3",  # DashScope embedding 模型
            input=texts,
            dimension=1024,  # 与 BGE-M3 对齐
        )

        if resp.status_code == 200:
            embeddings = [item["embedding"] for item in resp.output["embeddings"]]
            return np.array(embeddings, dtype=np.float32)
        else:
            logger.warning(f"[Embedding] DashScope API 错误: {resp.message}")
            return None
    except Exception as e:
        logger.warning(f"[Embedding] DashScope 调用失败: {e}")
        return None


def is_embedding_available() -> bool:
    """检查 Embedding 是否可用"""
    global _embedding_mode

    if _embedding_mode != "unavailable":
        return True

    # 尝试本地模型
    if _load_local_model():
        return True

    # 尝试 DashScope
    if settings.DASHSCOPE_API_KEY:
        _embedding_mode = "dashscope"
        return True

    return False


def embed_texts(texts: List[str], normalize: bool = True) -> np.ndarray:
    """
    批量文本向量化。

    Args:
        texts: 文本列表
        normalize: 是否 L2 归一化

    Returns:
        numpy array, shape=(len(texts), 1024)
    """
    if not texts:
        return np.array([])

    global _embedding_mode

    # 本地模型
    model = _load_local_model()
    if model:
        embeddings = model.encode(
            texts,
            normalize_embeddings=normalize,
            show_progress_bar=False,
        )
        _embedding_mode = "local"
        return embeddings

    # DashScope fallback
    batch_size = 20
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        batch_emb = _get_dashscope_embedding(batch)
        if batch_emb is not None:
            all_embeddings.append(batch_emb)
            _embedding_mode = "dashscope"
        else:
            # 降级为零向量
            logger.warning(f"[Embedding] DashScope 不可用，使用零向量降级")
            all_embeddings.append(np.zeros((len(batch), 1024), dtype=np.float32))

    return np.concatenate(all_embeddings, axis=0) if all_embeddings else np.array([])


def embed_text(text: str) -> np.ndarray:
    """单条文本向量化"""
    result = embed_texts([text])
    return result[0] if len(result) > 0 else np.zeros(1024, dtype=np.float32)


def embed_query(query: str) -> List[float]:
    """
    查询向量化（专用于检索）。

    当使用 BGE-M3 时，为 query 添加指令前缀以获得更好的检索效果。
    """
    # BGE 模型对 query 使用 instruction 前缀
    query_with_instruction = (
        f"为这个查询生成检索表示: {query}"
    )
    vec = embed_text(query_with_instruction)
    return vec.tolist()


def embed_documents(documents: List[str]) -> List[List[float]]:
    """
    文档向量化（用于存储到 Chroma）。

    BGE-M3 对文档不需要 instruction 前缀，直接编码即可。
    """
    vecs = embed_texts(documents)
    return vecs.tolist()


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """计算两个归一化向量的余弦相似度"""
    return float(np.dot(a, b))


def get_embedding_dim() -> int:
    """获取当前 Embedding 维度"""
    model = _load_local_model()
    if model:
        return model.get_embedding_dimension()
    return 1024  # BGE-M3 默认维度


def get_embedding_mode() -> str:
    """获取当前 Embedding 模式: local / dashscope / unavailable"""
    global _embedding_mode
    if _embedding_mode == "unavailable":
        is_embedding_available()
    return _embedding_mode
