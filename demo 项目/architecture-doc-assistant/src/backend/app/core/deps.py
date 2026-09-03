"""
依赖注入
========
FastAPI Depends 公共依赖：数据库会话、当前用户、权限校验。
"""

from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.security import decode_access_token

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> dict:
    """
    从 JWT 中提取当前用户信息。

    开发模式：不传 Token 时自动分配 guest 身份，避免前端调用 401。
    生产环境应改为 auto_error=True 强制认证。
    """
    if credentials is None:
        # 开发模式：匿名访问 = guest
        return {"user_id": "guest", "role": "viewer"}
    try:
        payload = decode_access_token(credentials.credentials)
        return {"user_id": payload["sub"], "role": payload["role"]}
    except Exception:
        # 开发模式：无效 Token 也降级为 guest
        return {"user_id": "guest", "role": "viewer"}


def require_role(*allowed_roles: str):
    """权限校验工厂函数"""

    async def role_checker(user: dict = Depends(get_current_user)):
        if user["role"] not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        return user

    return role_checker
