import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config

# 页面配置
from api_planning import ApiPlanningHub
from models import LargeLanguageModel

st.set_page_config(page_title="Copilot智能执行平台", layout="wide", initial_sidebar_state="expanded")

st.title("Copilot智能执行平台")
st.markdown("请在以下文本框输入**用户请求**")

# 输入框
text_input = st.text_area("text_input", height=68, placeholder="请输入用户请求")

# 初始化 session_state
if 'graph_data' not in st.session_state:
    st.session_state.graph_data = None
if 'agraph_config' not in st.session_state:
    st.session_state.agraph_config = None
if 'graph_ready' not in st.session_state:
    st.session_state.graph_ready = False
if 'selected_node_id' not in st.session_state:
    st.session_state.selected_node_id = None
if 'model_output' not in st.session_state:
    st.session_state.model_output = None

if 'text_ready' not in st.session_state:
    st.session_state.text_ready = False

if 'temperature' not in st.session_state:
    st.session_state.temperature = 0.1  # Default temperature

if 'api_url' not in st.session_state:
    st.session_state.api_url = ''

# Initialize session state for API key, supplier and temperature
if 'api_key' not in st.session_state:
    st.session_state.api_key = ''
if 'current_supplier' not in st.session_state:
    st.session_state.current_supplier = 'qwen-max'  # Default to zhipu


# 示例图数据生成函数
def generate_graph_data(text_input):
    uri = "http://localhost:19530"
    model_path = "model"
    db_name = "tool_db"
    model = st.session_state.current_supplier
    temperature = 0.01
    top_p = 0.01
    host = 'localhost'
    db = "tools"
    port = 27017
    topK = 7
    api_url = st.session_state.api_url
    api_key = st.session_state.api_key
    apiPlanningHub = ApiPlanningHub(uri, model_path, db_name, model, temperature, top_p, host, db, port, topK, api_url,
                                    api_key)

    results, model_output = apiPlanningHub.apis_planning(text_input)

    # {
    #     "code": 200,
    #     "tool": tool.name_for_human,
    #     "result": single_tool_response,
    #     "missing_param": get_missing_param,
    #     "param": params,
    #     "task_description": query
    # }

    nodes = []
    sub_nodes = []
    edges = []
    index = 1
    sub_index = 10000
    if model_output == "当前API无法实现用户需求":
        return [], [], model_output
    for tmp in results:
        if tmp["code"] == 404:
            return [], [], model_output
        nodes.append({
            "id": str(index),
            "label": tmp["tool"],
            "group": tmp["tool"],
            "task_description": tmp["task_description"],
            "params": tmp["param"],
            "result": tmp["result"],
        })
        for tmptmp in tmp["missing_param"]:
            sub_nodes.append({
                "id": str(sub_index),
                "label": tmptmp["tool"],
                "group": tmptmp["tool"],
                "task_description": tmptmp["task_description"],
                "params": tmptmp["param"],
                "result": tmptmp["result"]
            })
            edges.append({
                "from": str(sub_index),
                "to": str(index),
                "label": "缺省参数逆向API规划"
            })
            sub_index += 1
        index += 1
    if len(nodes) == 1:
        nodes = nodes + sub_nodes
        return nodes, edges, model_output
    for i in range(len(nodes) - 1):
        edges.append({
            "from": nodes[i]["id"],
            "to": nodes[i + 1]["id"],
            "label": "正向API规划"
        })
    nodes = nodes + sub_nodes
    return nodes, edges, model_output


# 转换为 agraph 格式
def prepare_graph_visualization(nodes_data, edges_data):
    nodes = [
        Node(id=str(node['id']), label=str(node['label']), size=25,
             color=f"#{hash(str(node['group'])) % 0xFFFFFF:06x}")
        for node in nodes_data
    ]
    edges = [
        Edge(source=str(edge['from']), target=str(edge['to']), label=str(edge['label']))
        for edge in edges_data
    ]
    config = Config(
        width=800, height=500, directed=True, physics=True, hierarchical=True,
        nodeHighlightBehavior=True, highlightColor="#F7A7A6", collapsible=True,
        node={'labelProperty': 'label'}, link={'labelProperty': 'label', 'renderLabel': True}
    )
    return nodes, edges, config


def test_llm():
    try:
        if len(st.session_state.api_key) != 0 and len(st.session_state.api_url) != 0 and len(
                st.session_state.current_supplier) != 0:
            llm = LargeLanguageModel(st.session_state.api_url, st.session_state.api_key)
            prompt ="""
You are an excellent API tool selection master. I will provide you with a task and provide information on candidate API tools. Please choose the best API to solve the task.

You have access to the following tools:

tool10: Call this tool to interact with the 查询物流供应商配送的订单信息 API.
What is the 查询物流供应商配送的订单信息 API useful for? 根据物流供应商ID查询该物流供应商配送的所有订单信息，例如查询由id为3物流供应商配送的所有订单信息 



tool15: Call this tool to interact with the 创建订单 API.
What is the 创建订单 API useful for? 根据用户ID、产品ID、数量、总价、物流供应商ID创建订单，例如创建一个产品ID为1，数量为100，配送区域为南京的订单        



tool13: Call this tool to interact with the 查询特定产品的订单信息 API.
What is the 查询特定产品的订单信息 API useful for? 根据产品的ID查询所有该产品的订单信息，例如请查询产品ID为1的订单信息



tool2: Call this tool to interact with the 根据配送区域查询供应商 API.
What is the 根据配送区域查询供应商 API useful for? 根据提供的配送区域查询供应商信息，例如：{"region": "区域1"}



tool17: Call this tool to interact with the 根据供应商名字查询物流供应商 API.
What is the 根据供应商名字查询物流供应商 API useful for? 根据提供的供应商名字查询供应商信息



tool16: Call this tool to interact with the 根据供应商状态查询物流供应商 API.
What is the 根据供应商状态查询物流供应商 API useful for? 根据提供的供应商状态查询供应商信息



tool14: Call this tool to interact with the 查询特定订单状态的订单信息 API.
What is the 查询特定订单状态的订单信息 API useful for? 根据订单状态查询所有该状态的订单信息，例如请查询运输中的订单信息


Please strictly follow the following rules:

1. the action to take, should be one of [tool10,tool15,tool13,tool2,tool17,tool16,tool14],
2. The output format is Action: toolX
3. Please output the results directly without any thought process
4. If there is no suitable API, please output None directly


Task: 请查询能够配送北京的物流供应商信息

Start!

            """
            results = llm.chat_completions(prompt, st.session_state.current_supplier, st.session_state.temperature,
                                           0.05)
            print(results)
            if len(results) != 0:
                st.success("大模型超参测试成功")
        else:
            st.error("大模型超参不正确")
    except:
        st.error("大模型调用失败")


# 提取按钮逻辑
def extract_knowledge():
    if not text_input:
        st.warning("Please enter text first.")
        return

    try:
        nodes_data, edges_data, model_output = generate_graph_data(text_input)
    except:
        nodes_data = []
        edges_data = []
        model_output = None
    print(model_output)
    if not model_output:
        st.session_state.text_ready = True
        st.session_state.model_output = model_output
    if not nodes_data:
        st.warning("Failed to extract valid knowledge graph.")
        st.session_state.graph_ready = False
        st.session_state.text_ready = True
        st.session_state.model_output = model_output
    else:
        st.session_state.graph_data = (nodes_data, edges_data)
        nodes, edges, config = prepare_graph_visualization(nodes_data, edges_data)
        st.session_state.agraph_config = {'nodes': nodes, 'edges': edges, 'config': config}
        st.session_state.graph_ready = True
        st.session_state.text_ready = True
        st.session_state.model_output = model_output


# 按钮点击
if st.button("Copilot 执行 "):
    with st.spinner('Copilot 执行中...'):
        extract_knowledge()

if st.session_state.text_ready and st.session_state.model_output:
    st.markdown("##### 执行结果")
    st.markdown(st.session_state.model_output)

# 使用列布局：左侧图，右侧信息
col1, col2 = st.columns([3.5, 1.5])

with col1:
    if st.session_state.graph_ready and st.session_state.agraph_config:
        st.markdown("#### API调用图谱")
        # 使用 container 和边框样式
        with st.container():
            return_value = agraph(
                nodes=st.session_state.agraph_config['nodes'],
                edges=st.session_state.agraph_config['edges'],
                config=st.session_state.agraph_config['config']
            )
            st.markdown("</div>", unsafe_allow_html=True)

        if return_value:
            st.session_state.selected_node_id = return_value

with col2:
    if st.session_state.graph_ready and st.session_state.agraph_config:
        # 节点详情卡片样式
        st.markdown("##### 节点详情")
        if st.session_state.selected_node_id:
            node_id = st.session_state.selected_node_id
            nodes_data, _ = st.session_state.graph_data
            node_info = next((n for n in nodes_data if n['id'] == node_id), None)

            if node_info:
                # 卡片样式
                st.markdown(
                    f"""
    <div style="
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 15px;
        background-color: #ffffff;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    ">
        <h4 style="margin-top:0; color: #333;">{node_info['label'] + " API"}</h4>
        <hr style="border: none; border-top: 1px solid #eee; margin: 10px 0;">
        <p style="margin: 4px 0;"><strong>子任务信息: </strong> {node_info['task_description']}</p>
         <hr style="border: none; border-top: 1px solid #eee; margin: 10px 0;">
        <p style="margin: 4px 0;"><strong>请求参数信息: </strong> {node_info["params"]}</p>
    </div>
    """,
                    unsafe_allow_html=True
                )
            else:
                st.write("未找到该节点的详细信息。")
        else:
            st.write("请点击图中的节点以查看详情。")


def setup_sidebar():
    """Setup sidebar for API key inputs"""
    with st.sidebar:
        st.header("大模型超参设置")
        # Add temperature slider
        # Add supplier selection dropdown
        supplier = st.selectbox(
            "请选择大模型",
            options=["qwen-max", "deepseek-v3"],
            index=0,  # Default to zhipu
            key="supplier_select"
        )
        st.session_state.current_supplier = supplier

        # Add temperature slider
        temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=1.0,
            value=st.session_state.temperature,
            step=0.1,
            help="Higher values make the output more random, lower values make it more focused and deterministic"
        )
        st.session_state.temperature = temperature

        # Single API key input
        api_url = st.text_input(
            f"Enter {supplier.upper()} API URL",
            type="password",
            value=st.session_state.api_url,
            key="api_url_input"
        )
        if api_url:
            st.session_state.api_url = api_url

        # Single API key input
        api_key = st.text_input(
            f"Enter {supplier.upper()} API Key",
            type="password",
            value=st.session_state.api_key,
            key="api_key_input"
        )
        if api_key:
            st.session_state.api_key = api_key

        if st.button("大模型超参测试"):
            with st.spinner('大模型超参测试中 ....'):
                test_llm()


def main():
    setup_sidebar()
    # Rest of your application code...


if __name__ == "__main__":
    main()
