import re
from typing import List, Tuple

# 内置词表（若文件不存在则使用此内置列表）
BUILTIN_WORDS = [
    "100%纯天然", "100%满意", "100%安全", "best", "best seller", "best-selling",
    "畅销", "销量第一", "第一", "top 1", "top one", "number one", "#1",
    "perfect", "完美", "excellent", "极好", "最高级", "最好", "独一无二",
    "唯一", "only", "unstoppable", "不可阻挡", "guarantee", "guaranteed",
    "保证", "承诺", "无风险", "risk-free", "no risk", "零风险", "zero risk",
    "绝对", "absolutely", "definitely", "certainly", "毫无疑问",
    "no side effects", "无副作用", "副作用为零", "永久", "permanent",
    "forever", "everlasting", "never fade", "永不褪色", "instant",
    "instant cure", "立即见效", "magic", "神奇", "miracle", "奇迹",
    "unbelievable", "难以置信"
]

def load_sensitive_words(file_path: str = None) -> List[str]:
    """加载敏感词，如果文件不存在则返回内置词表（大小写归一化）"""
    if file_path:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                words = [line.strip().lower() for line in f if line.strip()]
            return words
        except FileNotFoundError:
            pass
    return [w.lower() for w in BUILTIN_WORDS]

def filter_sensitive(text: str, words_list: List[str]) -> Tuple[str, List[str]]:
    """
    对文本进行敏感词过滤，返回 (高亮后的HTML文本, 命中的词列表)
    匹配策略：全词匹配（单词边界），中文直接用包含匹配（简单实现）
    """
    if not text:
        return text, []
    
    text_lower = text.lower()
    hits = []
    
    # 为了做边界匹配，先将原文本按空格/标点分词，但简单起见，直接用 in 匹配并高亮
    # 对英文词做 \b 边界，中文直接用字符串包含（避免"best"匹配到"beautiful"）
    # MVP阶段：简单替换，同时记录命中词
    highlighted = text
    for word in words_list:
        # 对中文或英文分别处理，这里简化：使用 re.IGNORECASE + 边界
        # 英文词加 \b，中文直接用 re.escape
        if re.match(r'^[a-zA-Z\s\-]+$', word):  # 纯英文或英文+空格/连字符
            pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
        else:
            pattern = re.compile(re.escape(word), re.IGNORECASE)
        
        if pattern.search(text):
            hits.append(word)
            # 高亮：用红色标记（仅第一次替换防止嵌套，但简单循环）
            # 用替换方法加span
            highlighted = pattern.sub(lambda m: f'<span style="color:red;font-weight:bold;">{m.group()}</span>', highlighted)
    
    # 去重
    hits = list(set(hits))
    return highlighted, hits