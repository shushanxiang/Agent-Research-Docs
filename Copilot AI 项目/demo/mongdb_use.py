import os
from mongoengine import connect, disconnect, get_connection
from entity.user_entity import User
from entity.tool_entity import Tool, Parameter

# MongoDB连接配置
MONGO_HOST = "127.0.0.1"
MONGO_DB = "test"
MONGO_PORT = 27017

def connect_mongodb():
    """连接到MongoDB数据库"""
    try:
        # 检查是否已有连接
        existing_connection = get_connection()
        if existing_connection:
            disconnect()  # 断开现有连接
    except Exception as e:
        print(f"检查已有MongoDB连接时出错: {e}，将重新建立连接。")
    
    # 建立新的MongoDB连接
    client = connect(MONGO_DB, host=MONGO_HOST, port=MONGO_PORT)
    print(f"成功连接到MongoDB: {MONGO_HOST}:{MONGO_PORT}/{MONGO_DB}")
    return client

def create_user(user_id, username, password):
    """创建用户 - 增加操作"""
    try:
        user = User(
            user_id=user_id,
            userName=username,
            password=password
        )
        user.save()
        print(f"成功创建用户: {username}")
        return user
    except Exception as e:
        print(f"创建用户失败: {e}")
        return None

def get_user(username):
    """获取用户信息 - 查询操作"""
    try:
        user = User.objects(userName=username).first()
        if user:
            print(f"找到用户: {user.userName}, ID: {user.user_id}")
            return user
        else:
            print(f"未找到用户: {username}")
            return None
    except Exception as e:
        print(f"查询用户失败: {e}")
        return None

def update_user(username, new_password):
    """更新用户信息 - 修改操作"""
    try:
        user = User.objects(userName=username).first()
        if user:
            user.password = new_password
            user.save()
            print(f"成功更新用户密码: {username}")
            return user
        else:
            print(f"未找到用户: {username}")
            return None
    except Exception as e:
        print(f"更新用户失败: {e}")
        return None

def delete_user(username):
    """删除用户 - 删除操作"""
    try:
        user = User.objects(userName=username).first()
        if user:
            user.delete()
            print(f"成功删除用户: {username}")
            return True
        else:
            print(f"未找到用户: {username}")
            return False
    except Exception as e:
        print(f"删除用户失败: {e}")
        return False

def list_all_users():
    """列出所有用户"""
    try:
        users = User.objects()
        print(f"共找到 {users.count()} 个用户:")
        for user in users:
            print(f"  - ID: {user.user_id}, Username: {user.userName}")
        return list(users)
    except Exception as e:
        print(f"查询用户列表失败: {e}")
        return []

def main():
    """主函数，演示MongoDB的基本操作"""
    print("MongoDB基本操作示例")
    print("=" * 30)
    
    # 连接到MongoDB
    client = connect_mongodb()
    
    # 清理可能存在的测试数据
    User.objects(userName="test_user").delete()
    User.objects(userName="updated_user").delete()
    Tool.objects(operationId="test_operation").delete()
    
    print("\n--- 用户操作示例 ---")
    
    # 创建用户 (增加操作)
    print("\n1. 创建用户:")
    user1 = create_user(1001, "test_user", "password123")
    
    # 查询用户 (查询操作)
    print("\n2. 查询用户:")
    user_found = get_user("test_user")
    
    # 更新用户 (修改操作)
    print("\n3. 更新用户:")
    update_user("test_user", "newpassword456")
    
    # 再次查询验证更新
    print("\n4. 验证更新:")
    get_user("test_user")
    
    # 创建另一个用户进行列表展示
    create_user(1002, "updated_user", "anotherpass")
    
    # 列出所有用户
    print("\n5. 列出所有用户:")
    list_all_users()
    
    # 删除用户 (删除操作)
    print("\n6. 删除用户:")
    delete_user("test_user")
    
    # 验证删除
    print("\n7. 验证删除:")
    get_user("test_user")

    print("\n--- 示例结束 ---")

if __name__ == "__main__":
    main()
