import logging
import time
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse, quote
from fastapi import APIRouter, Query, Response, HTTPException
import httpx

from app.models.media import ApiResponse, BangumiItem, BangumiWeekday
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bangumi", tags=["Bangumi"])

# In-memory cache for calendar: (timestamp, List[BangumiWeekday])
_calendar_cache: Optional[tuple[float, List[BangumiWeekday]]] = None

async def _fetch_calendar_raw() -> List[Dict[str, Any]]:
    """
    Fetches Bangumi calendar.
    Attempts mirror first (bangumi.vip), then falls back to official api.bgm.tv endpoint.
    """
    headers = {
        "User-Agent": "MediaCenter/1.0.0 (https://center.amm114514.cc.cd)",
        "Accept": "application/json"
    }

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
        # 1. Try mirror bangumi.vip
        try:
            resp = await client.get(settings.BANGUMI_MIRROR_URL)
            if resp.status_code == 200:
                ct = resp.headers.get("content-type", "")
                if "application/json" in ct or resp.text.strip().startswith("["):
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        logger.info("Successfully fetched Bangumi calendar from mirror bangumi.vip")
                        return data
        except Exception as e:
            logger.debug(f"bangumi.vip mirror fetch skipped/failed: {e}")

        # 2. Resilient fallback to official api.bgm.tv
        try:
            resp = await client.get(settings.BANGUMI_API_URL)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    logger.info("Successfully fetched Bangumi calendar from official api.bgm.tv")
                    return data
        except Exception as e:
            logger.error(f"api.bgm.tv fetch failed: {e}")

    return []

def _parse_calendar(raw_data: List[Dict[str, Any]]) -> List[BangumiWeekday]:
    weekdays: List[BangumiWeekday] = []
    for day in raw_data:
        w_info = day.get("weekday", {})
        w_id = w_info.get("id", 1)
        w_cn = w_info.get("cn", f"星期{w_id}")
        w_en = w_info.get("en", "")

        items: List[BangumiItem] = []
        for it in day.get("items", []):
            b_id = it.get("id")
            if not b_id:
                continue
            name = it.get("name", "").strip()
            name_cn = it.get("name_cn", "").strip() or name
            air_date = it.get("air_date")
            air_weekday = it.get("air_weekday", w_id)

            rating_info = it.get("rating", {})
            score = rating_info.get("score") if isinstance(rating_info, dict) else None

            images = it.get("images") or {}
            raw_cover = images.get("large") or images.get("common") or images.get("medium")
            cover = raw_cover
            if raw_cover and ("bgm.tv" in raw_cover or "bangumi.tv" in raw_cover):
                cover = f"/api/v1/bangumi/cover?url={quote(raw_cover, safe='')}"

            items.append(BangumiItem(
                id=b_id,
                name=name,
                name_cn=name_cn,
                air_date=air_date,
                air_weekday=air_weekday,
                score=score,
                cover=cover,
                summary=it.get("summary")
            ))

        # Sort: items with score first, highest score descending
        items.sort(key=lambda x: (x.score is not None, x.score or 0), reverse=True)

        weekdays.append(BangumiWeekday(
            weekday_id=w_id,
            weekday_cn=w_cn,
            weekday_en=w_en,
            items=items
        ))

    # Ensure days are sorted Mon (1) to Sun (7)
    weekdays.sort(key=lambda w: w.weekday_id)
    return weekdays

@router.get("/calendar", response_model=ApiResponse[List[BangumiWeekday]])
async def get_anime_calendar():
    """
    获取每日新番更新时刻表 (周一至周日)
    含动画中文译名、首播日期、评分、封面海报
    """
    global _calendar_cache
    now = time.time()

    if _calendar_cache is not None:
        cached_time, cached_data = _calendar_cache
        if now - cached_time < settings.BANGUMI_CACHE_TTL and cached_data:
            return ApiResponse(code=0, message="ok (cached)", data=cached_data)

    raw_data = await _fetch_calendar_raw()
    if not raw_data and _calendar_cache is not None:
        # Fall back to stale cache if upstream is unavailable
        return ApiResponse(code=0, message="ok (stale cache)", data=_calendar_cache[1])

    weekdays = _parse_calendar(raw_data)
    if weekdays:
        _calendar_cache = (now, weekdays)

    return ApiResponse(
        code=0,
        message=f"ok (fetched {sum(len(w.items) for w in weekdays)} anime across 7 days)",
        data=weekdays
    )

@router.post("/calendar/refresh", response_model=ApiResponse[dict])
async def refresh_calendar():
    """强制重新拉取 Bangumi 新番日历"""
    global _calendar_cache
    raw_data = await _fetch_calendar_raw()
    weekdays = _parse_calendar(raw_data)
    if weekdays:
        _calendar_cache = (time.time(), weekdays)
    total_count = sum(len(w.items) for w in weekdays)
    return ApiResponse(code=0, message="calendar refreshed", data={"total_anime": total_count})

@router.get("/cover")
async def get_bangumi_cover(url: str = Query(..., description="Bangumi image URL to proxy")):
    """
    Image proxy for Bangumi posters.
    Caches image with 30-day Cache-Control for Cloudflare Edge & client caching.
    """
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="Invalid URL protocol")
    
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not (host == "lain.bgm.tv" or host.endswith(".bgm.tv") or host.endswith(".bangumi.tv")):
        raise HTTPException(status_code=403, detail="Forbidden: Only Bangumi domains allowed")
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://bangumi.tv/",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                ct = resp.headers.get("content-type", "image/jpeg")
                return Response(
                    content=resp.content,
                    media_type=ct,
                    headers={
                        "Cache-Control": "public, max-age=2592000, s-maxage=2592000, immutable",
                        "Access-Control-Allow-Origin": "*",
                    }
                )
    except Exception as e:
        logger.warning(f"Failed to fetch Bangumi cover from {url}: {e}")
        
    raise HTTPException(status_code=404, detail="Image not found")
