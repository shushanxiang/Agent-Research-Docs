"""
检索服务路由
============
POST /regulations  — 规范条款检索 (从共享索引)
POST /atlas        — 图集节点检索
"""

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.core.registry import get_search_service

router = APIRouter()


@router.post("/regulations")
async def search_regulations(
    body: dict,
    user: dict = Depends(get_current_user),
):
    """规范条款检索 — 从已上传文档的共享索引中查询"""
    query = body.get("query", "")
    filters = body.get("filters")
    top_k = body.get("top_k", 10)

    svc = get_search_service()
    result = svc.search_regulations(query, filters=filters, top_k=top_k)

    if result["total"] == 0:
        return {
            "total": 0,
            "results": [],
            "hint": "当前索引为空，请先上传规范文档(.pdf/.txt)到「文档管理」页面",
        }

    return result


@router.post("/atlas")
async def search_atlas(
    body: dict,
    user: dict = Depends(get_current_user),
):
    """图集节点多维度检索"""
    from app.core.registry import get_search_service as svc
    return svc().search_atlas(
        query=body.get("query"),
        atlas_code=body.get("atlas_code"),
        node_id=body.get("node_id"),
        material=body.get("material"),
    )
