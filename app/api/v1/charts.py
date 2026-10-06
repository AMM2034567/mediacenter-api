import logging
from typing import List
from fastapi import APIRouter, Query, HTTPException
from app.models.media import ApiResponse
from app.models.chart import ChartCategory, ChartItem
from app.sources.chart_manager import ChartManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/charts", tags=["Charts & Rankings"])

@router.get("/categories", response_model=ApiResponse[List[ChartCategory]])
async def get_chart_categories():
    """
    获取精选影视榜单与豆瓣专区分类列表
    """
    mgr = ChartManager.get_instance()
    cats = mgr.get_categories()
    return ApiResponse(code=0, message="ok", data=cats)

@router.get("/{category_id}", response_model=ApiResponse[List[ChartItem]])
async def get_chart_items(
    category_id: str,
    page: int = Query(1, ge=1, le=20, description="页码"),
    limit: int = Query(20, ge=1, le=50, description="每页返回数量")
):
    """
    获取指定分类榜单内容 (如 豆瓣Top250、热门电影、国产热播、欧美剧集、动漫新番等)
    """
    mgr = ChartManager.get_instance()
    items = await mgr.get_chart_items(category_id, page=page, limit=limit)
    return ApiResponse(code=0, message="ok", data=items)
