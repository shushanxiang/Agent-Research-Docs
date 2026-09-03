import gradio as gr
from graph.workflow import build_workflow
from graph.state import AgentState
from db.duckdb_manager import SessionDB
from config import DB_PATH
import uuid
import inspect

db_manager = SessionDB(DB_PATH)
workflow = build_workflow(db_manager)

# 存储每个会话的状态（Gradio State）
sessions = {}

def process_message(message, history, session_state):
    """处理用户消息和文件"""
    if not session_state:  # None 或空 dict（Gradio State 初始值）都需初始化
        session_id = str(uuid.uuid4())
        session_state = {
            "session_id": session_id,
            "messages": [],
            "uploaded_files": [],
            "execution_result": None
        }
        sessions[session_id] = session_state
    
    # 将用户消息加入历史
    session_state["messages"].append({"role": "user", "content": message})
    
    # 注入当前会话的uploaded_files与图片（若有）
    state = AgentState(
        messages=session_state["messages"],
        session_id=session_state["session_id"],
        uploaded_files=session_state.get("uploaded_files", []),
        current_image_url=session_state.get("current_image_url", None),
        execution_result=None,
        error=None
    )
    
    # 执行LangGraph
    try:
        result = workflow.invoke(state)
    except Exception as e:
        # 兜底：任何工作流异常都转成友好提示，避免请求中断导致前端连接错误
        reply = f"⚠️ 处理失败：{type(e).__name__}: {e}\n请检查数据文件格式或稍后重试。"
        session_state["messages"].append({"role": "assistant", "content": reply})
        sessions[session_state["session_id"]] = session_state
        return reply, session_state
    
    # 提取回复
    final_output = result.get("execution_result", {})
    reply = ""
    
    if final_output.get("type") == "data":
        # 数据表格展示（前10行，Markdown）
        records = final_output.get("dataframe", [])
        if records:
            cols = list(records[0].keys())
            table_lines = [
                "| " + " | ".join(str(c) for c in cols) + " |",
                "|" + "---|" * len(cols),
            ]
            for row in records[:10]:
                table_lines.append("| " + " | ".join(str(row.get(c, "")) for c in cols) + " |")
            reply += "\n".join(table_lines) + "\n"
            total = final_output.get("total_rows", len(records))
            if total > 10:
                reply += f"\n*（仅显示前 10 行，共 {total} 行）*\n"
        # 回答式总结
        reply += f"\n📊 {final_output.get('summary', '')}\n"
        if final_output.get("chart"):
            reply += f'<img src="{final_output["chart"]}" alt="chart" style="max-width:100%;"/>'
        reply += f"\n\nSQL: `{final_output.get('sql', '')}`"
    
    elif final_output.get("type") == "listing":
        for lst in final_output.get("listings", []):
            reply += f"### {lst['style']}\n"
            reply += lst.get("filtered_html", lst.get("raw", ""))
            if lst.get("has_issue"):
                reply += "\n\n⚠️ 检测到敏感词：" + ", ".join(lst.get("hits", []))
            reply += "\n\n---\n"
    
    elif final_output.get("type") == "image":
        for img in final_output.get("images", []):
            reply += f"**{img['style']} + {img['scene']}**\n"
            reply += f'<img src="{img["url"]}" style="max-width:200px;margin:5px;"/>'
            reply += "\n"
    
    elif final_output.get("type") == "evaluate":
        reply += f"### 综合评分：{final_output.get('score', 0)}/100\n"
        reply += "**各维度得分：**\n"
        for k, v in final_output.get("detail", {}).items():
            reply += f"- {k}: {v}/20\n"
        reply += "\n**改进建议：**\n"
        for s in final_output.get("suggestions", []):
            reply += f"- {s}\n"
    
    else:
        reply = "暂未识别您的意图，请尝试：查询数据 / 生成Listing / 生成图片 / 评估Listing"
    
    # 更新会话状态
    session_state["messages"].append({"role": "assistant", "content": reply})
    sessions[session_state["session_id"]] = session_state
    
    return reply, session_state

def upload_file(file, session_state):
    """文件上传回调"""
    if not session_state:  # None 或空 dict（Gradio State 初始值）都需初始化
        session_id = str(uuid.uuid4())
        session_state = {"session_id": session_id, "messages": [], "uploaded_files": []}
        sessions[session_id] = session_state
    
    # 导入数据到DuckDB
    table_name = db_manager.upload_file(
        session_state["session_id"],
        file.name,
        file.name
    )
    session_state["uploaded_files"].append(table_name)
    sessions[session_state["session_id"]] = session_state
    return f"✅ 文件上传成功！已导入表: {table_name}，当前共 {len(session_state['uploaded_files'])} 个文件。", session_state


def upload_image(image_path, session_state):
    """产品图片上传回调（用于 Listing 生成 / 场景图生成）"""
    if not session_state:
        session_id = str(uuid.uuid4())
        session_state = {"session_id": session_id, "messages": [], "uploaded_files": [], "current_image_url": None}
        sessions[session_id] = session_state
    session_state["current_image_url"] = image_path
    sessions[session_state["session_id"]] = session_state
    return f"✅ 产品图片已上传！可输入：生成Listing / 生成场景图。", session_state

# Gradio 界面
# 版本兼容：gradio 6.x 起 Blocks 不再接受 theme 参数，仅旧版本传入
_blocks_kwargs = {"title": "跨境电商运营助手"}
if "theme" in inspect.signature(gr.Blocks.__init__).parameters:
    _blocks_kwargs["theme"] = gr.themes.Soft()

with gr.Blocks(**_blocks_kwargs) as demo:
    gr.Markdown("# 🌍 跨境电商运营助手（AI Agent）")
    gr.Markdown("支持：📊 数据查询分析 | 📝 Listing生成 | 🖼️ 图片生成 | 📈 质量评估")
    
    session_state = gr.State({})
    
    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(label="对话窗口", height=600)
            msg = gr.Textbox(label="输入指令", placeholder="例如：展示上周每日销售额趋势图", lines=2)
            send_btn = gr.Button("发送")
        with gr.Column(scale=1):
            file_upload = gr.File(label="上传数据文件 (CSV/XLSX)", file_types=[".csv", ".xlsx"])
            upload_status = gr.Textbox(label="上传状态", interactive=False)
            image_upload = gr.Image(label="上传产品图片（Listing生成/场景图）", type="filepath", height=200)
            gr.Markdown("### 提示：\n- 上传文件后，用自然语言查询\n- 生成Listing：上传图片并说“生成3种风格Listing”\n- 评估：说“评估这条Listing”")
    
    def chat_response(message, history, state):
        reply, new_state = process_message(message, history, state)
        # Gradio 6 的 Chatbot 仅支持 messages 格式（role/content 字典），
        # 不再支持旧版 (user, bot) 二元组
        if history is None:
            history = []
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": reply})
        return history, "", new_state
    
    def upload_response(file, state):
        status, new_state = upload_file(file, state)
        return status, new_state

    def image_response(image, state):
        status, new_state = upload_image(image, state)
        return status, new_state
    
    send_btn.click(
        chat_response,
        inputs=[msg, chatbot, session_state],
        outputs=[chatbot, msg, session_state]
    )
    msg.submit(
        chat_response,
        inputs=[msg, chatbot, session_state],
        outputs=[chatbot, msg, session_state]
    )
    file_upload.upload(
        upload_response,
        inputs=[file_upload, session_state],
        outputs=[upload_status, session_state]
    )
    image_upload.upload(
        image_response,
        inputs=[image_upload, session_state],
        outputs=[upload_status, session_state]
    )

if __name__ == "__main__":
    demo.launch(share=True, debug=True)