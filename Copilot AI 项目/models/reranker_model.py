# coding = utf-8
"""
BGE重排序模型实现
使用modelscope上的BAAI/bge-reranker-v2-m3模型
"""

import torch
# from transformers import AutoModelForSequenceClassification, AutoTokenizer
# import torch.nn.functional as F
import os

from utils import logger


class BGEReranker:
    def __init__(self, model_name="BAAI/bge-reranker-v2-m3", use_fp16=True, use_modelscope=True):
        """
        初始化BGE重排序模型
        
        Args:
            model_name (str): 模型名称，默认为"BAAI/bge-reranker-v2-m3"
            use_fp16 (bool): 是否使用半精度浮点数
            use_modelscope (bool): 是否使用ModelScope而不是Hugging Face
        """
        self.model_name = model_name
        self.use_fp16 = use_fp16
        
        # 初始化日志
        self.logger = logger.getLogger(__name__)
        
        try:
            # 检查是否使用ModelScope
            if use_modelscope:
                # 使用ModelScope
                from modelscope import AutoModelForSequenceClassification, AutoTokenizer
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
            else:
                # 使用Hugging Face
                from transformers import AutoModelForSequenceClassification, AutoTokenizer
                # 检查是否有Hugging Face令牌
                token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")
                
                # 加载分词器
                if token:
                    self.tokenizer = AutoTokenizer.from_pretrained(model_name, token=token)
                    # 加载模型
                    self.model = AutoModelForSequenceClassification.from_pretrained(model_name, token=token)
                else:
                    self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                    # 加载模型
                    self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
            
            # 设置设备
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.model = self.model.to(self.device)
            
            # 如果支持且启用，使用半精度
            if use_fp16 and torch.cuda.is_available():
                self.model = self.model.half()
                
            # 设置为评估模式
            self.model.eval()
            
            self.logger.info(f"BGE重排序模型加载成功，使用设备: {self.device}")
            
        except Exception as e:
            self.logger.error(f"加载BGE重排序模型失败: {e}")
            raise e
    
    def rerank(self, query, candidates, return_scores=False):
        """
        对候选结果进行重排序
        
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
            # 构建查询-候选对
            pairs = [[query, candidate] for candidate in candidates]
            
            # 批量编码
            with torch.no_grad():
                inputs = self.tokenizer(
                    pairs,
                    padding=True,
                    truncation=True,
                    return_tensors='pt',
                    max_length=512
                ).to(self.device)
                
                # 模型推理
                scores = self.model(**inputs, return_dict=True).logits.view(-1, ).float()
                scores = torch.sigmoid(scores)
                
                # 转换为CPU numpy数组
                scores_cpu = scores.cpu().numpy()
                
                # 获取排序索引（降序）
                sorted_indices = scores_cpu.argsort()[::-1]
                
                if return_scores:
                    return sorted_indices.tolist(), scores_cpu.tolist()
                else:
                    return sorted_indices.tolist()
                    
        except Exception as e:
            self.logger.error(f"重排序过程中发生错误: {e}")
            # 如果重排序失败，返回原始顺序
            original_indices = list(range(len(candidates)))
            if return_scores:
                return original_indices, [0.0] * len(candidates)
            else:
                return original_indices
    
    def rerank_with_details(self, query, candidates):
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
        for idx in sorted_indices:
            reranked_results.append({
                'index': idx,
                'text': candidates[idx],
                'score': scores[idx]
            })
            
        return reranked_results

# 单例模式确保只加载一次模型
_reranker_instance = None

def get_reranker_instance(use_modelscope=True):
    """
    获取重排序模型单例实例
    
    Args:
        use_modelscope (bool): 是否使用ModelScope而不是Hugging Face
    """
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = BGEReranker(use_modelscope=use_modelscope)
    return _reranker_instance