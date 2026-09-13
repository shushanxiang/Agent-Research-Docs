from mongoengine import StringField, IntField, Document, ListField


class User(Document):
    user_id = IntField(required=True)
    userName = StringField(unique=True, required=True)
    password = StringField(required=True)
    user_authority = ListField(StringField(), default=[])