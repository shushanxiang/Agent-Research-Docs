from mongoengine import EmbeddedDocument, EmbeddedDocumentField, StringField, BooleanField, ListField, IntField, \
    Document

# Parameter 类用于表示工具参数的文档模型，包含参数的名称、是否必填、类型、描述、可选枚举值和默认值等信息。

class Parameter(EmbeddedDocument):
    name = StringField()
    required = BooleanField()
    type = StringField()
    format = StringField()
    description = StringField()
    enum = ListField(StringField())
    value = StringField()
    in_ = StringField()

# Tool 类用于表示工具的文档模型，包含工具的 ID、操作 ID、名称、模型名称、描述、API URL、路径、方法、请求体等信息。
class Tool(Document):
    tool_id = IntField()
    isValidate = BooleanField()
    operationId = StringField()
    name_for_human = StringField()
    name_for_model = StringField()
    description = StringField()
    api_url = StringField()
    path = StringField()
    method = StringField()
    request_body = ListField(EmbeddedDocumentField(Parameter))
