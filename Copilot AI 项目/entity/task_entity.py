from mongoengine import Document, StringField, ListField, DictField, IntField


class Task(Document):
    task_id = StringField() # 任务的唯一性编号
    status = IntField() # 任务的状态
    task_type = IntField()  # 任务的类型
    raw_query = StringField() # 用户的最初查询请求
    changed_query = StringField()  # 查询请求，最初与raw_query一致，任务执行中间可能发生变化
    curr_task_desc = StringField() # 任务的当前描述，一般由大模型依据用户的最初查询请求生成也可以是任务执行过程中描述
    nodes = ListField(DictField()) # 前端界面调用链展示部分
    edges = ListField(DictField()) # 前端界面调用链展示部分
    graph_title = StringField()  # 前端界面调用链展示部分的标题
    system_output = StringField() # 任务的结果文字输出
    curr_tool_id = IntField() # 当前等待被确认的工具ID
    curr_tool_param = DictField() # 当前等待被确认的工具ID的参数
    # 方案 11 新增：版本号与审计日志
    version = IntField(default=0)       # 版本号，乐观锁，每次 update 递增
    feedback_log = ListField(DictField(), default=list)  # 反馈审计日志

    def to_dict(self):
        """将 Task 对象转换为字典，前端页面使用"""
        return {
            'task_id': self.task_id,
            'status': self.status,
            'nodes': self.nodes,
            'edges': self.edges,
            'isSuccess': self.graph_title,
            'systemOutput': self.system_output
        }