import uuid
from mongoengine import *
import threading
from cachetools import TTLCache

from entity import Parameter, Tool, Task
from utils import logger, TASK_STATUS_INIT, TASK_STATUS_FINISH, TASK_INIT_TOOL_ID, TASK_TYPE_UNKNOWN, \
    TASK_TYPE_MAINTAIN, TASK_SYS_OUTPUT_STOP
import traceback


class TaskManager:
    """
    task实例和状态管理，提供task的生命周期管理方法，在数据库中新建任务、更新任务等。

    __init__ 方法获得访问数据库的连接和设置并发控制。
    """
    def __init__(self, mongo_host, mongo_db, mongo_port):
        self.mongoClient = connect(mongo_db, host=mongo_host, port=mongo_port)
        self.cache_lock = threading.Lock()

    def create_task(self, user_raw_query: str, exists_task_id: str = "") -> Task:
        """
        创建任务
        """
        if not exists_task_id:
            new_task_status = TASK_STATUS_INIT
            system_output = "正在初始化任务......"
            while True:
                # 创建任务ID，并保证唯一性
                task_id = str(uuid.uuid4())
                task = Task.objects(task_id=task_id).first()
                if task is None:
                    break
        else:
            task_id = exists_task_id
            new_task_status = TASK_STATUS_FINISH
            system_output = TASK_SYS_OUTPUT_STOP + "该任务早已结束，请重新登录"
        task = Task()
        task.task_id = task_id
        task.status = new_task_status
        task.task_type = TASK_TYPE_UNKNOWN
        task.raw_query = user_raw_query
        task.changed_query = user_raw_query
        task.curr_task_desc = ""
        task.edges = []
        task.nodes = []
        task.system_output = system_output
        task.curr_tool_id = TASK_INIT_TOOL_ID
        task.curr_tool_param = {}
        task.save()
        return task

    def update_task_recorder(self, task_id: str, task_status: int, system_output: str, graph_title: str = "",
                            curr_task_desc="", task_type: int = TASK_TYPE_MAINTAIN, nodes: list = None,
                            edges: list = None, curr_tool_id: int = 0, curr_tool_param: dict = None,changed_query="",
                            feedback_entry: dict = None) -> str:
        """
        更新任务表update_task
        """
        try:
            task = Task.objects.get(task_id=task_id)
            logger.debug(f"准备更新表中的任务task= {task.task_id}: task_status={task.status},nodes={task.nodes}, edges={task.edges}, "
                        f"curr_task_desc={task.curr_task_desc},systemOutput={task.system_output}, graph_title={task.graph_title}, task_type={task.task_type},"
                        f"curr_tool_id={task.curr_tool_id}, curr_tool_param={task.curr_tool_param},changed_query={task.changed_query} ")
            logger.debug(f"更新为 task= {task_id}: task_status={task_status},nodes={nodes}, edges={edges}, "
                        f"curr_task_desc={curr_task_desc},systemOutput={system_output}, graph_title={graph_title}, task_type={task_type},"
                        f"curr_tool_id={curr_tool_id}, curr_tool_param={curr_tool_param},changed_query={changed_query} ")
            task.status = task_status
            task.system_output = system_output
            task.graph_title = graph_title
            if changed_query:
                task.changed_query = changed_query
            if curr_task_desc:
                task.curr_task_desc = curr_task_desc
            if task_type:
                task.task_type = task_type
            if nodes:
                task.nodes = nodes
            if edges:
                task.edges = edges
            if curr_tool_id:
                task.curr_tool_id = curr_tool_id
            if curr_tool_param:
                task.curr_tool_param = curr_tool_param

            # 方案 11：版本号递增 + 反馈审计日志
            task.version = (task.version or 0) + 1
            if feedback_entry:
                feedback_entry["version"] = task.version
                task.feedback_log.append(feedback_entry)
                logger.debug(f"任务{task_id}记录反馈日志 v{task.version}: intent={feedback_entry.get('intent')}")

            task.save()
            task_saved = Task.objects.get(task_id=task_id)
            logger.debug(f"更新后表中的任务task= {task_saved.task_id}: task_status={task_saved.status},nodes={task_saved.nodes}, edges={task_saved.edges}, "
                        f"curr_task_desc={task_saved.curr_task_desc},systemOutput={task_saved.system_output}, graph_title={task_saved.graph_title}, task_type={task_saved.task_type},"
                        f"curr_tool_id={task_saved.curr_tool_id}, curr_tool_param={task_saved.curr_tool_param},changed_query={task_saved.changed_query}")
            return task_id
        #TODO DoesNotExist是个什么？
        except Task.DoesNotExist:
            logger.error(f"任务[{task_id}]不存在")
            # 可以选择创建新任务或返回错误
        except Exception as e:
            logger.error(f"任务[{task_id}]保存失败: {e}\n{traceback.format_exc()}")
            raise  e

    def get_task_by_id(self, task_id) -> Task| None:
        """
        通过task_id获得任务实体
        """
        try:
            task = Task.objects.get(task_id=task_id)
            return task
        except Task.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"获取任务[{task_id}]失败: {e}\n{traceback.format_exc()}")
            return None
