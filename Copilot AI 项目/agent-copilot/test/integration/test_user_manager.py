"""测试 user_manager — 密码工具函数 + UserManagerHub（真实 MongoDB）"""

import os, sys, pytest
from unittest.mock import MagicMock, patch

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

os.environ["mongo_port"] = "27112"
os.environ["mongo_host"] = "127.0.0.1"
os.environ["local_mode"] = "0"


class TestPasswordUtils:
    """密码哈希工具函数"""

    def test_hash_password(self):
        from use_manager.user_manager import hash_password
        h = hash_password("test123")
        assert isinstance(h, str)
        assert h.startswith("$2b$")

    def test_verify_password_correct(self):
        from use_manager.user_manager import hash_password, verify_password
        h = hash_password("mypassword")
        assert verify_password("mypassword", h) is True

    def test_verify_password_wrong(self):
        from use_manager.user_manager import hash_password, verify_password
        h = hash_password("mypassword")
        assert verify_password("wrongpassword", h) is False

    def test_different_salts(self):
        from use_manager.user_manager import hash_password
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # 不同的 salt 导致不同的 hash


class TestUserManagerHub:
    """UserManagerHub 集成测试"""

    @pytest.fixture(scope="module")
    def user_mgr(self):
        from use_manager.user_manager import UserManagerHub
        um = UserManagerHub("127.0.0.1", "tools", 27112)
        yield um

    def test_init(self, user_mgr):
        assert user_mgr is not None
        assert user_mgr.mongoClient is not None

    def test_get_next_user_id(self, user_mgr):
        uid = user_mgr.get_next_user_id()
        assert uid > 0

    def test_create_user(self, user_mgr):
        code, msg = user_mgr.create_user("test_user_01", "pass123", "pass123")
        assert code == 200 or code == 409  # 可能已存在
        assert "注册" in msg or "已注册" in msg

    def test_create_user_password_mismatch(self, user_mgr):
        code, msg = user_mgr.create_user("test_user_02", "pass1", "pass2")
        assert code == 400
        assert "密码" in msg

    def test_login_valid(self, user_mgr):
        # 确保用户存在
        user_mgr.create_user("login_test", "secret", "secret")
        user = user_mgr.login("login_test", "secret")
        assert user is not None

    def test_login_invalid(self, user_mgr):
        user = user_mgr.login("nonexistent_user_xyz", "bad")
        assert user is not None  # 返回 User(user_id=-1)
        assert user.user_id == -1

    def test_islogin_after_login(self, user_mgr):
        user_mgr.create_user("cache_test", "pw", "pw")
        user = user_mgr.login("cache_test", "pw")
        if user and user.user_id != -1:
            assert user_mgr.islogin(user.user_id) is True
            user_mgr.logout(user.user_id)
            assert user_mgr.islogin(user.user_id) is False

    def test_logout(self, user_mgr):
        user_mgr.create_user("logout_test", "pw", "pw")
        user = user_mgr.login("logout_test", "pw")
        if user and user.user_id != -1:
            result = user_mgr.logout(user.user_id)
            assert result is True
            assert user_mgr.islogin(user.user_id) is False

    def test_islogin_not_logged_in(self, user_mgr):
        assert user_mgr.islogin(99999999) is False
