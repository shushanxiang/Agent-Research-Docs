import json
import time
from typing import List
from mongoengine import *
import threading
from entity import User
from cachetools import TTLCache
import bcrypt
from utils import logger, DEFAULT_PERMISSIONS
import traceback


def hash_password(password: str) -> str:
    """对密码进行哈希加密"""
    # 生成盐值并加密密码
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed_password: str) -> bool:
    """验证密码是否正确"""
    return bcrypt.checkpw(
        password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )

class UserManagerHub:
    def __init__(self, mongo_host, mongo_db, mongo_port):
        self.mongoClient = connect(mongo_db, host=mongo_host, port=mongo_port)
        self.db_name = mongo_db  # 保存数据库名称
        self.cache_lock = threading.Lock()
        self.user_cache = TTLCache(maxsize=100, ttl=3600)

    def get_next_user_id(self):
        db = self.mongoClient[self.db_name]
        # 使用findAndModify原子操作
        counter = db.mongoClient.counters.find_one_and_update(
            {"_id": "user_id"},
            {"$inc": {"sequence_value": 1}},
            upsert=True,
            return_document=True
        )
        return counter["sequence_value"]

    def create_user(self, user_name, password, confirm_password, permissions=None):
        if password != confirm_password:
            return 400, "两次输入的密码不一致"

        try:
            # 先检查用户名是否存在
            if User.objects(userName=user_name).first():
                return 409, "该用户已注册"

            # 原子获取用户ID
            user_id = self.get_next_user_id()
            password = hash_password(password)
            # 设置默认权限
            if permissions is None:
                permissions = DEFAULT_PERMISSIONS
            # 创建用户
            current_user = User(user_id=user_id, userName=user_name, password=password, user_authority=permissions)
            current_user.save()
            return 200, "用户注册成功"
        except NotUniqueError:
            return 409, "用户已存在"
        except Exception as e:
            logger.error(f"注册失败: {e}\n{traceback.format_exc()}")
            return 500, f"注册失败: {str(e)}"

    def login(self, user_name, password):
        try:
            users = User.objects(userName=user_name)
            if users:
                user = users.first()
                stored_password = user.password
                if isinstance(stored_password, str):
                    stored_password = stored_password.encode('utf-8')
                if bcrypt.checkpw(password.encode('utf-8'), stored_password):
                    with self.cache_lock:
                        self.user_cache[user.user_id] = user
                    return user
        except Exception as e:
            logger.error(f"登录失败: {e}\n{traceback.format_exc()}")
        return User(user_id=-1)

    def logout(self, user_id):
        with self.cache_lock:
            self.user_cache.pop(user_id, None)
        return True

    def islogin(self,user_id):
        user = self.user_cache.get(user_id)
        if user is None:
            return False
        else:
            return True
