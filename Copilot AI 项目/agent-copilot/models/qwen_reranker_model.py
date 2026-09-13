# coding = utf-8
"""
通义千问gte-rerank-v2模型实现
通过API调用通义千问的重排序服务
"""

from typing import List, Tuple, Union
import dashscope
from http import HTTPStatus

from utils import logger


class QwenReranker:
    def __init__(self, api_key: str):
        """
        初始化通义千问重排序模型
        Args:
            api_key (str): 通义千问API密钥
        """
        self.api_key = api_key
        # 设置API密钥
        dashscope.api_key = api_key

    def rerank(self, query: str, candidates: List[str], return_scores: bool = False) -> Union[List[int], Tuple[List[int], List[float]]]:
        """
        使用通义千问gte-rerank-v2模型对候选结果进行重排序
        Args:
            query (str): 查询文本
            candidates (list): 候选文本列表
            return_scores (bool): 是否返回分数
        Returns:
            list: 重排序后的候选结果索引列表，或(索引列表, 分数列表)元组
        """
        if not candidates:
            return [] if not return_scores else ([], [])
        try:
            # 调用通义千问文本重排序API
            response = dashscope.TextReRank.call(
                model="gte-rerank-v2",
                query=query,
                documents=candidates,
                top_n=len(candidates),  # 返回所有候选文档
                return_documents=True
            )
            # 检查响应状态
            if response.status_code == HTTPStatus.OK:
                results = response.output.results
                # 提取索引和分数
                indices = [item["index"] for item in results]
                scores = [item["relevance_score"] for item in results]

                if return_scores:
                    return indices, scores
                else:
                    return indices
            else:
                logger.error(f"通义千问重排序API调用失败，状态码: {response.status_code}, 错误信息: {response.message}")
                # 如果API调用失败，返回原始顺序
                original_indices = list(range(len(candidates)))
                if return_scores:
                    return original_indices, [0.0] * len(candidates)
                else:
                    return original_indices

        except Exception as e:
            logger.error(f"通义千问重排序过程中发生错误: {e}")
            # 如果重排序失败，返回原始顺序
            original_indices = list(range(len(candidates)))
            if return_scores:
                return original_indices, [0.0] * len(candidates)
            else:
                return original_indices

    def rerank_with_details(self, query: str, candidates: List[str]) -> List[dict]:
        """
        对候选结果进行重排序并返回详细信息
        Args:
            query (str): 查询文本
            candidates (list): 候选文本列表

        Returns:
            list: 包含候选文本和对应分数的排序列表
        """
        sorted_indices, scores = self.rerank(query, candidates, return_scores=True)
        reranked_results = []
        for i, idx in enumerate(sorted_indices):
            reranked_results.append({
                'index': idx,
                'text': candidates[idx],
                'score': scores[i]
            })

        return reranked_results

# 单例模式确保只创建一次实例
_qwen_reranker_instance = None

def get_qwen_reranker_instance(api_key: str):
    """
    获取通义千问重排序模型单例实例
    Args:
        api_key (str): 通义千问API密钥
    """
    global _qwen_reranker_instance
    if _qwen_reranker_instance is None:
        _qwen_reranker_instance = QwenReranker(api_key=api_key)
    return _qwen_reranker_instance