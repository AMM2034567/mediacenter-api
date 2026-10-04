import asyncio
import logging
from typing import List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.models.media import SourceInfo, AnimeSourceInfo, ApiResponse
from app.sources.manager import SourceManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sources", tags=["Sources"])

class RefreshRequest(BaseModel):
    url: Optional[str] = None

@router.get("", response_model=ApiResponse[List[SourceInfo]])
async def list_sources():
    """
    获取当前后端注册的所有可用影视源列表
    若距上次同步超过 12 小时 (TTL)，将自动请求 GitHub 拉取最新订阅配置
    """
    source_mgr = SourceManager.get_instance()
    if source_mgr.need_refresh():
        try:
            logger.info("Daily TTL expired, refreshing sources from GitHub subscription...")
            await asyncio.wait_for(source_mgr.reload_from_remote(), timeout=5.0)
        except Exception as e:
            logger.warning(f"Auto daily source refresh failed or timed out: {e}")

    sources = source_mgr.list_sources()
    return ApiResponse(
        code=0,
        message=f"total {len(sources)} sources",
        data=sources
    )

@router.get("/anime", response_model=ApiResponse[List[AnimeSourceInfo]])
async def list_anime_sources():
    """
    获取动漫专属专线源列表 (来自 creamy cake 专线订阅)
    """
    sources = SourceManager.get_instance().list_anime_sources()
    return ApiResponse(
        code=0,
        message=f"total {len(sources)} anime sources",
        data=sources
    )


@router.get("/cron", response_model=ApiResponse[dict])
@router.post("/refresh", response_model=ApiResponse[dict])
async def refresh_sources(body: Optional[RefreshRequest] = None):
    """
    手动调用或由 Vercel Cron 每日定时任务调用：从 GitHub 重新拉取最新订阅并同步影视源
    """
    custom_url = body.url if body else None
    source_mgr = SourceManager.get_instance()
    count = await source_mgr.reload_from_remote(url=custom_url)
    return ApiResponse(
        code=0,
        message="sources refreshed successfully",
        data={"total_sources": count}
    )
