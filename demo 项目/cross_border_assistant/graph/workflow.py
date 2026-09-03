from functools import partial
from langgraph.graph import StateGraph, END
from graph.state import AgentState
from graph.supervisor import supervisor_node
from graph.data_agent import data_agent_node
from graph.text_agent import text_agent_node
from graph.image_agent import image_agent_node
from graph.evaluator import evaluator_node

def route_after_supervisor(state: AgentState) -> str:
    """路由函数"""
    intent = state.get("intent", "unknown")
    if intent == "data":
        return "data_agent"
    elif intent == "listing":
        return "text_agent"
    elif intent == "image":
        return "image_agent"
    elif intent == "evaluate":
        return "evaluator"
    else:
        return "data_agent"  # 默认走数据

def build_workflow(db_manager=None):
    """构建 LangGraph 工作流。

    参数 db_manager：data_agent 节点需要访问会话数据库（SessionDB 实例）。
    若不传则使用默认路径的 SessionDB（config.DB_PATH）。
    """
    if db_manager is None:
        from db.duckdb_manager import SessionDB
        from config import DB_PATH
        db_manager = SessionDB(DB_PATH)

    builder = StateGraph(AgentState)
    
    # 添加节点
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("data_agent", partial(data_agent_node, db_manager=db_manager))
    builder.add_node("text_agent", text_agent_node)
    builder.add_node("image_agent", image_agent_node)
    builder.add_node("evaluator", evaluator_node)
    
    # 入口
    builder.set_entry_point("supervisor")
    
    # 条件边
    builder.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "data_agent": "data_agent",
            "text_agent": "text_agent",
            "image_agent": "image_agent",
            "evaluator": "evaluator",
        }
    )
    
    # 所有Agent执行完后直接结束
    builder.add_edge("data_agent", END)
    builder.add_edge("text_agent", END)
    builder.add_edge("image_agent", END)
    builder.add_edge("evaluator", END)
    
    return builder.compile()