from typing import List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.models.media import SourceInfo, ApiResponse
from app.sources.manager import SourceManager

router = APIRouter(prefix="/sources", tags=["Sources"])

class RefreshRequest(BaseModel):
    url: Optional[str] = None

@router.get("", response_model=ApiResponse[List[SourceInfo]])
async def list_sources():
    """
    获取当前后端注册的所有可用影视源列表
    """
    source_mgr = SourceManager.get_instance()
    sources = source_mgr.list_sources()
    return ApiResponse(
        code=0,
        message=f"total {len(sources)} sources",
        data=sources
    )

@router.post("/refresh", response_model=ApiResponse[dict])
async def refresh_sources(body: Optional[RefreshRequest] = None):
    """
    手动或定时触发：从远程 GitHub 重新拉取最新 Base58 配置并更新源列表
    """
    custom_url = body.url if body else None
    source_mgr = SourceManager.get_instance()
    count = await source_mgr.reload_from_remote(url=custom_url)
    return ApiResponse(
        code=0,
        message="sources refreshed successfully",
        data={"total_sources": count}
    )
