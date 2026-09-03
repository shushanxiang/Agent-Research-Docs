"""
Streamlit 前端主入口
====================
建筑智能文档助手 — 规范检索 | 图集检索 | 智能问答 | 文档管理

所有页面通过 HTTP 调用 FastAPI 后端 (http://localhost:8000)。
"""

import json

import httpx
import streamlit as st

st.set_page_config(
    page_title="建筑智能文档助手",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── API 配置 ──
API_BASE = "http://localhost:8000"
API_TIMEOUT = 30

# ── Session state 初始化 ──
if "token" not in st.session_state:
    st.session_state.token = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


def api_call(method: str, path: str, **kwargs) -> dict | None:
    """统一的 API 调用封装"""
    url = f"{API_BASE}{path}"
    headers = kwargs.pop("headers", {})
    if st.session_state.token:
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    try:
        with httpx.Client(timeout=API_TIMEOUT) as client:
            resp = client.request(method, url, headers=headers, **kwargs)
            if resp.status_code == 200:
                return resp.json()
            else:
                st.error(f"API 错误 ({resp.status_code}): {resp.text[:200]}")
                return None
    except httpx.ConnectError:
        st.error(f"后端服务未启动，请检查 {API_BASE} 是否运行")
        return None
    except httpx.ReadTimeout:
        st.error("请求超时，请稍后重试")
        return None
    except Exception as e:
        st.error(f"请求异常: {e}")
        return None


# ── UI 头部 ──
st.title("建筑智能文档助手")
st.caption("规范法规查询 | 做法图集问答 | 企业知识沉淀")

# 侧边连接状态
with st.sidebar:
    st.header("导航")
    page = st.radio(
        "选择页面",
        ["首页", "文档管理", "规范检索", "图集检索", "智能问答"],
    )
    st.divider()
    # 连接状态
    try:
        r = httpx.get(f"{API_BASE}/health", timeout=3)
        if r.status_code == 200:
            d = r.json()
            st.success(f"🟢 后端已连接 (v{d.get('version','?')})")
        else:
            st.warning("🟡 后端响应异常")
    except Exception:
        st.error("🔴 后端未连接")

# ═══════════════════════════════════════════════════════════
#  首页
# ═══════════════════════════════════════════════════════════
if page == "首页":
    st.markdown("## 欢迎使用建筑智能文档助手")
    st.markdown("""
    本平台基于 RAG 架构，为建筑行业提供：
    - **文档统一存储与版本管理** — 告别文件夹+微信传文件
    - **规范条款智能检索** — 自然语言提问，秒级定位条款
    - **图集节点图文问答** — 上传图集，看图说话
    - **企业知识沉淀** — 企业标准做法系统化积累
    """)

    # 快捷入口
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔍 规范检索", use_container_width=True):
            st.session_state["nav_to"] = "规范检索"
            st.rerun()
    with col2:
        if st.button("📐 图集检索", use_container_width=True):
            st.session_state["nav_to"] = "图集检索"
            st.rerun()
    with col3:
        if st.button("💬 智能问答", use_container_width=True):
            st.session_state["nav_to"] = "智能问答"
            st.rerun()

# ═══════════════════════════════════════════════════════════
#  文档管理
# ═══════════════════════════════════════════════════════════
elif page == "文档管理":
    st.header("📄 文档管理")

    # 上传
    uploaded_file = st.file_uploader(
        "上传建筑文档",
        type=["pdf", "jpg", "png", "docx", "xlsx", "pptx", "txt"],
        accept_multiple_files=False,
    )
    category = st.selectbox("文档类型", ["规范", "图集", "图纸", "报告", "施工日志", "变更单"], index=0)

    if uploaded_file and st.button("上传并解析"):
        with st.spinner("正在上传并解析文档..."):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            data = {"category": category, "version_strategy": "auto_increment"}
            result = api_call("POST", "/api/v1/documents/upload", files=files, data=data)
            if result:
                parser = result.get("parser", "")
                chunks = result.get("chunks_indexed", 0)
                st.success(
                    f"上传成功！解析引擎: {parser}  |  已拆分 {chunks} 个 chunk 入库"
                )
                # 元数据
                meta = result.get("metadata", {})
                if meta:
                    with st.expander("📋 提取的元数据"):
                        st.json(meta)
                # Markdown 预览
                md_url = result.get("markdown_url", "")
                doc_id = result.get("document_id", "")
                if doc_id:
                    detail = api_call("GET", f"/api/v1/documents/{doc_id}")
                    full_md = detail.get("full_markdown", "") if detail else ""
                    if full_md:
                        with st.expander("📝 解析结果 (Markdown 预览)", expanded=True):
                            st.markdown(full_md)
                elif md_url:
                    st.info(f"📝 Markdown 文件已保存: `{md_url}`")

    st.divider()

    # 文档列表
    st.subheader("已上传文档")
    if st.button("刷新列表"):
        docs = api_call("GET", "/api/v1/documents/")
        if docs:
            items = docs.get("items", [])
            if items:
                for d in items:
                    parser_info = d.get("parser", "未知")
                    with st.expander(
                        f"{d.get('filename','')} ({d.get('category','')})"
                    ):
                        st.caption(
                            f"状态: {d.get('status','')}  |  "
                            f"大小: {d.get('file_size',0)} bytes  |  "
                            f"解析引擎: {parser_info}"
                        )
                        meta = d.get("metadata", {})
                        if meta:
                            st.json(meta)
                        # Markdown 预览
                        full_md = d.get("full_markdown", "")
                        if full_md:
                            st.divider()
                            st.markdown("**📝 解析结果 (Markdown 预览):**")
                            st.markdown(full_md)
                        else:
                            raw = d.get("raw_text", "")
                            if raw:
                                st.text_area("解析文本", raw, height=150)
            else:
                st.info("暂无上传的文档")

# ═══════════════════════════════════════════════════════════
#  规范检索
# ═══════════════════════════════════════════════════════════
elif page == "规范检索":
    st.header("🔍 规范检索")

    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input(
            "输入检索关键词或自然语言提问",
            placeholder="如：商场疏散宽度、外墙保温材料燃烧性能、防火分区面积",
        )
    with col2:
        top_k = st.number_input("返回条数", min_value=1, max_value=20, value=5)

    if query and st.button("检索", type="primary"):
        with st.spinner("正在检索..."):
            result = api_call(
                "POST", "/api/v1/search/regulations",
                json={"query": query, "top_k": top_k},
            )
            if result:
                total = result.get("total", 0)
                results = result.get("results", [])
                st.success(f"找到 {total} 条相关条款")

                for i, item in enumerate(results):
                    score = item.get("score", 0)
                    clause_id = item.get("clause_id", "")
                    status = item.get("status", "有效")
                    status_color = "red" if status == "废止" else "green"

                    with st.container():
                        st.markdown(f"### #{i+1}  {item.get('standard_title', '')}  "
                                    f"`{item.get('standard_code', '')}`  "
                                    f"第{clause_id}条")
                        st.caption(f"📄 {item.get('chapter_path', '')}")
                        st.info(item.get("content", ""))
                        c1, c2 = st.columns([1, 4])
                        with c1:
                            st.metric("相关度", f"{score:.2%}")
                        with c2:
                            st.markdown(f"状态: :{status_color}[{status}]")
                        st.divider()

# ═══════════════════════════════════════════════════════════
#  图集检索
# ═══════════════════════════════════════════════════════════
elif page == "图集检索":
    st.header("📐 图集检索")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        query = st.text_input(
            "输入做法关键词",
            placeholder="如：屋面防水上人屋面做法、种植屋面、外墙保温节点",
        )
    with col2:
        atlas_code = st.text_input("图集编号（可选）", placeholder="如：12J201")
    with col3:
        material = st.text_input("材料名称（可选）", placeholder="如：SBS防水卷材")

    if query and st.button("检索", type="primary"):
        with st.spinner("正在检索..."):
            result = api_call(
                "POST", "/api/v1/search/atlas",
                json={
                    "query": query,
                    "atlas_code": atlas_code or None,
                    "material": material or None,
                },
            )
            if result:
                total = result.get("total", 0)
                results = result.get("results", [])
                st.success(f"找到 {total} 个匹配节点")

                for item in results:
                    with st.container():
                        st.markdown(
                            f"### {item.get('node_id', '')} — {item.get('node_name', '')}")
                        st.caption(
                            f"📐 《{item.get('atlas_title', '')}》"
                            f"{item.get('atlas_code', '')}  |  "
                            f"第{item.get('page_num', '?')}页")
                        st.info(item.get("description", ""))
                        mats = item.get("materials", [])
                        if mats:
                            st.markdown("**材料清单:** " +
                                        ", ".join(f"`{m}`" for m in mats))
                        st.metric("相关度", f"{item.get('similarity_score',0):.2%}")
                        st.divider()

# ═══════════════════════════════════════════════════════════
#  智能问答
# ═══════════════════════════════════════════════════════════
elif page == "智能问答":
    st.header("💬 智能问答")

    # 模式
    mode = st.radio("问答模式", ["规范问答", "图集问答"], horizontal=True)

    question = st.text_area(
        "输入您的问题",
        placeholder=(
            "如：6层住宅楼需要设电梯吗"
            if mode == "规范问答"
            else "如：屋面防水上人屋面的正置式和倒置式做法有什么区别？"
        ),
        height=80,
    )

    if st.button("提问", type="primary", disabled=not question):
        if mode == "规范问答":
            with st.spinner("AI 正在检索和分析..."):
                result = api_call(
                    "POST", "/api/v1/chat/regulation",
                    json={
                        "question": question,
                        "chat_history": st.session_state.chat_history,
                        "top_k": 5,
                    },
                )
                if result:
                    # 回答
                    st.markdown("### 📝 回答")
                    st.markdown(result.get("answer", ""))

                    # 溯源
                    sources = result.get("sources", [])
                    if sources:
                        st.divider()
                        st.markdown("### 📚 引用条款")
                        for s in sources:
                            abolished = s.get("is_abolished", False)
                            tag = " ⚠️已废止" if abolished else ""
                            with st.expander(
                                f"《{s.get('standard_title','')}》"
                                f"{s.get('standard_code','')} "
                                f"第{s.get('clause_id','')}条{tag}"
                            ):
                                st.text(s.get("content", ""))
                                st.caption(f"相关度: {s.get('score',0):.2%}")

                    # 免责
                    st.caption(result.get("disclaimer", ""))

                    # 更新历史
                    st.session_state.chat_history.append(
                        {"role": "user", "content": question})
                    st.session_state.chat_history.append(
                        {"role": "assistant", "content": result.get("answer", "")})

        else:  # 图集问答
            with st.spinner("AI 正在分析图集做法..."):
                result = api_call(
                    "POST", "/api/v1/chat/atlas",
                    json={"question": question},
                )
                if result:
                    st.markdown("### 📝 回答")
                    st.markdown(result.get("answer", ""))
                    st.caption(result.get("disclaimer", ""))

    # 历史对话
    if st.session_state.chat_history:
        st.divider()
        st.markdown("### 💭 对话历史")
        for msg in st.session_state.chat_history:
            role = "🧑 你" if msg["role"] == "user" else "🤖 AI"
            with st.chat_message("user" if msg["role"] == "user" else "assistant"):
                st.markdown(msg["content"])
