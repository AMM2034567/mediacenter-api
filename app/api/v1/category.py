import asyncio
import logging
import time
from typing import List, Optional, Dict
from fastapi import APIRouter, Query
import httpx

from app.models.media import SearchItem, ApiResponse, MediaType
from app.sources.manager import SourceManager
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/category", tags=["Category"])

# In-memory cache for category listings: { "cat:page:src": (timestamp, items) }
_category_cache: Dict[str, tuple[float, List[SearchItem]]] = {}

MOVIE_KEYWORDS = ["电影", "动作片", "喜剧片", "爱情片", "科幻片", "恐怖片", "剧情片", "战争片", "纪录片", "灾难片", "悬疑片", "犯罪片", "奇幻片"]
SERIES_KEYWORDS = ["电视剧", "国产剧", "美剧", "韩剧", "日剧", "泰剧", "港剧", "台剧", "海外剧", "剧集", "短剧"]
ANIME_KEYWORDS = ["动漫", "动画", "番剧", "国创", "日漫", "欧美动漫", "新番"]
VARIETY_KEYWORDS = ["综艺", "真人秀", "脱口秀", "晚会", "选秀"]

def match_category(type_name: str, target_cat: str) -> bool:
    if not type_name:
        return target_cat in ("all", "")
    t = type_name.strip()
    if target_cat == "anime":
        return any(k in t for k in ANIME_KEYWORDS)
    elif target_cat == "movie":
        return any(k in t for k in MOVIE_KEYWORDS) and not any(k in t for k in ANIME_KEYWORDS)
    elif target_cat == "series":
        return any(k in t for k in SERIES_KEYWORDS) and not any(k in t for k in ANIME_KEYWORDS)
    elif target_cat == "variety":
        return any(k in t for k in VARIETY_KEYWORDS)
    return True

@router.get("", response_model=ApiResponse[List[SearchItem]])
async def browse_category(
    cat: str = Query("all", description="专区分类: all(全部), movie(电影), series(电视剧), anime(动漫), variety(综艺)"),
    page: int = Query(1, ge=1, le=100, description="页码"),
    limit: int = Query(30, ge=1, le=100, description="每页返回数量"),
    source: Optional[str] = Query(None, description="指定源key")
):
    """
    分类专区浏览接口：按电影、电视剧、动漫、综艺等专区流式浏览最新更新资源
    """
    cat_normalized = cat.lower().strip()
    cache_key = f"{cat_normalized}:{page}:{source or 'default'}"
    now = time.time()

    if cache_key in _category_cache:
        cached_time, cached_items = _category_cache[cache_key]
        if now - cached_time < 600:  # 10 minutes cache
            return ApiResponse(code=0, message="ok (cached)", data=cached_items[:limit])

    source_mgr = SourceManager.get_instance()
    
    # Select high-speed sources for browsing
    # For anime, prioritize dedicated anime source if present
    target_source = None
    if source:
        target_source = source_mgr.get_source(source)
    elif cat_normalized == "anime":
        target_source = source_mgr.get_source("caiji.moduapi.cc") or source_mgr.get_source("dbzy.tv")
    else:
        target_source = source_mgr.get_source("dbzy.tv") or source_mgr.get_source("iqiyizyapi.com")

    if not target_source:
        active = source_mgr.list_sources()
        if active:
            target_source = active[0]
        else:
            return ApiResponse(code=0, message="no active sources", data=[])

    items: List[SearchItem] = []
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        ) as client:
            resp = await client.get(
                target_source.api,
                params={"ac": "detail", "pg": page},
                timeout=settings.UPSTREAM_TIMEOUT
            )
            if resp.status_code == 200:
                data = resp.json()
                raw_list = data.get("list", [])
                for vod in raw_list:
                    vod_id = str(vod.get("vod_id", ""))
                    vod_name = vod.get("vod_name", "").strip()
                    if not vod_id or not vod_name:
                        continue

                    type_name = vod.get("type_name", "")
                    if cat_normalized != "all" and not match_category(type_name, cat_normalized):
                        continue

                    m_type = MediaType.ANIME if any(k in type_name for k in ANIME_KEYWORDS) else MediaType.VIDEO

                    items.append(SearchItem(
                        id=f"maccms:{target_source.key}:{vod_id}",
                        title=vod_name,
                        cover=vod.get("vod_pic"),
                        source_key=target_source.key,
                        source_name=target_source.name,
                        remarks=vod.get("vod_remarks"),
                        type_name=type_name,
                        year=str(vod.get("vod_year", "")) if vod.get("vod_year") else None,
                        area=vod.get("vod_area"),
                        media_type=m_type
                    ))

    except Exception as e:
        logger.error(f"Category browse error for {target_source.name}: {e}")

    _category_cache[cache_key] = (now, items)

    return ApiResponse(
        code=0,
        message=f"fetched {len(items)} items in category '{cat_normalized}'",
        data=items[:limit]
    )
