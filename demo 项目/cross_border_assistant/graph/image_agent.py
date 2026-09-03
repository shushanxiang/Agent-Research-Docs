from graph.state import AgentState, get_last_content
from dashscope import ImageSynthesis
from config import IMAGE_GEN_MODEL, IMAGE_GEN_CONFIG
import time

def image_agent_node(state: AgentState) -> dict:
    """通义万相图片生成：支持纯文生图与基于主图生成场景图"""
    user_query = get_last_content(state)
    main_image = state.get("current_image_url")  # 用户上传的主图（可选）
    # 解析用户需求：如"正面/侧面/俯视"和"户外/室内"
    # 简单示例：固定生成4张
    styles = ["正面视角", "侧面视角", "俯视视角"]
    scenes = ["户外背景", "室内背景"]

    results = []
    for style in styles[:2]:  # 简化：只生2角度×2场景=4张
        for scene in scenes:
            if main_image:
                prompt = f"基于上传的产品主图，生成电商场景图：{style}，{scene}，保持产品主体与外观一致，高清，4k"
            else:
                prompt = f"电商产品图，{style}，{scene}，高清，产品居中，纯白背景或自然光，4k"
            try:
                response = ImageSynthesis.call(
                    model=IMAGE_GEN_MODEL,
                    prompt=prompt,
                    width=IMAGE_GEN_CONFIG["width"],
                    height=IMAGE_GEN_CONFIG["height"],
                    n=1
                )
                if response.status_code == 200:
                    img_url = response.output.results[0].url
                else:
                    img_url = f"生成失败: {response.message}"
            except Exception as e:
                img_url = f"异常: {e}"

            results.append({
                "style": style,
                "scene": scene,
                "url": img_url,
                "based_on_main_image": bool(main_image),
            })
            time.sleep(0.5)  # 避免限频

    return {"execution_result": {"type": "image", "images": results}}