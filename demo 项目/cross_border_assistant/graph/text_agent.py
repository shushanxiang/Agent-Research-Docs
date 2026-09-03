from graph.state import AgentState, get_last_content
from utils.llm_client import call_vl, call_llm
from utils.sensitive_words import load_sensitive_words, filter_sensitive

def text_agent_node(state: AgentState) -> dict:
    """文本生成Agent：如果有图片则先VL识别，再生成3种风格Listing，最后敏感词过滤"""
    user_query = get_last_content(state)
    # 假设前端将图片URL传入了state（简化：从query中提取，或从Gradio组件传参）
    # 这里占位：实际使用时，Gradio将上传的图片URL作为参数传入，我们暂从state取
    image_url = state.get("current_image_url", None)  # 外部注入
    
    # 1. 识别图片（VL 不可用时降级为纯文本生成，不崩溃）
    image_desc = ""
    vl_ok = False
    if image_url:
        try:
            image_desc = call_vl(image_url, "请详细描述这张产品的材质、颜色、形状、使用场景和核心卖点，适合电商详情页。")
            if image_desc and not image_desc.startswith("VL Error") and "失败" not in image_desc:
                vl_ok = True
        except Exception:
            image_desc = ""
    if image_url and not vl_ok:
        image_desc = "（图片识别服务暂不可用，请基于文字描述生成）"
    
    # 2. 生成Listing（3种风格）
    style_names = ["专业严谨型", "促销冲动型", "场景体验型"]
    listings = []
    
    for style in style_names:
        prompt = f"""基于以下产品信息生成一条完整的亚马逊Listing（英文），包含：
- Title (不超过200字符)
- 5 Bullet Points (每个短句)
- Product Description (一段话)
- Search Keywords (逗号分隔)

产品识别信息：{image_desc}
用户要求关键词：{user_query}
风格要求：{style}

直接输出文本，不要markdown标记。
"""
        content = call_llm(prompt, system_prompt="你是有10年经验的跨境电商文案专家。")
        if content.startswith("LLM调用失败"):
            # LLM 不可用（如 API 额度耗尽）：标记该风格失败，不执行敏感词过滤
            listings.append({
                "style": style,
                "raw": content,
                "filtered_html": content,
                "hits": [],
                "has_issue": False,
                "llm_error": content,
            })
            continue
        
        # 3. 敏感词过滤
        words_list = load_sensitive_words()
        filtered_html, hits = filter_sensitive(content, words_list)
        
        listings.append({
            "style": style,
            "raw": content,
            "filtered_html": filtered_html,
            "hits": hits,
            "has_issue": len(hits) > 0
        })
    
    return {"execution_result": {"type": "listing", "listings": listings, "image_desc": image_desc}}