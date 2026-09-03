from typing import List, Dict, Any, TypedDict, Optional
from langgraph.graph.message import add_messages
from typing import Annotated


def get_last_content(state: Dict[str, Any]) -> str:
    """安全获取最后一条消息的文本内容。

    兼容两种形态：
    - langgraph 1.x 下 messages 经 add_messages 归约为 BaseMessage 对象（用 .content 访问）
    - 直接构造的 dict 消息（用 ["content"] 访问）
    """
    last = state["messages"][-1]
    if hasattr(last, "content"):
        return last.content
    return last["content"]


class AgentState(TypedDict):
    """全局状态"""
    messages: Annotated[List[Dict[str, str]], add_messages]  # [{"role": "user"/"assistant", "content": "..."}]
    session_id: str
    intent: Optional[str]                # data | listing | image | evaluate | mixed
    data_type: Optional[str]             # data 子类型: trend | stat | list | predict | vague
    need_image: Optional[bool]           # 该任务是否需要图片输入
    current_image_url: Optional[str]     # 用户上传的图片路径/URL（外部注入）
    uploaded_files: List[str]            # 表名列表
    execution_result: Optional[Dict[str, Any]]  # 各Agent的输出汇总
    error: Optional[str]