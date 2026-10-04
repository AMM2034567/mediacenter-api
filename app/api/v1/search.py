import asyncio
import logging
import time
from typing import List, Optional, Dict
from fastapi import APIRouter, Query, HTTPException
import httpx

from app.models.media import SearchItem, ApiResponse
from app.sources.manager import SourceManager
from app.sources.maccms import MacCMSDriver
from app.api.v1.category import match_category
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["Search"])

# Simple in-memory cache for search results: { cache_key: (timestamp, results) }
_search_cache: Dict[str, tuple[float, List[SearchItem]]] = {}

@router.get("", response_model=ApiResponse[List[SearchItem]])
async def search_media(
    kw: str = Query(..., min_length=1, description="搜索关键词，如：凡人修仙传、三体"),
    source: Optional[str] = Query(None, description="指定数据源key，不传则全网多源并发搜索"),
    category: Optional[str] = Query(None, description="分类过滤: all, movie, series, anime, variety"),
    limit: int = Query(50, ge=1, le=200, description="返回的最大条数")
):
    keyword = kw.strip()
    cat_normalized = (category or "all").lower().strip()
    cache_key = f"{keyword}:{source or 'all'}:{cat_normalized}"
    
    # Check cache
    now = time.time()
    if cache_key in _search_cache:
        cached_time, cached_items = _search_cache[cache_key]
        if now - cached_time < settings.SEARCH_CACHE_TTL:
            return ApiResponse(code=0, message="ok (cached)", data=cached_items[:limit])

            
    source_mgr = SourceManager.get_instance()
    
    # Determine target sources to search
    if source:
        src = source_mgr.get_source(source)
        if not src:
            raise HTTPException(status_code=404, detail=f"Source key '{source}' not found")
        target_sources = [src]
    else:
        target_sources = [s for s in source_mgr.list_sources() if s.is_active]
        
    if not target_sources:
        return ApiResponse(code=0, message="no active sources", data=[])
        
    all_results: List[SearchItem] = []
    
    # Run async queries in parallel across all target sources
    async with httpx.AsyncClient(
        limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    ) as client:
        tasks = [
            MacCMSDriver.search(
                client=client,
                site_key=src.key,
                site_name=src.name,
                api_url=src.api,
                keyword=keyword
            )
            for src in target_sources
        ]
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for res in responses:
            if isinstance(res, list):
                all_results.extend(res)
            elif isinstance(res, Exception):
                logger.debug(f"Search task exception: {res}")
                
    if cat_normalized != "all":
        all_results = [item for item in all_results if match_category(item.type_name or "", cat_normalized)]

    # Reliability and match relevance scoring
    reliable_source_scores: Dict[str, float] = {
        "dyttzyapi.com": 120.0,
        "cj.lzcaiji.com": 110.0,
        "bfzy.tv": 105.0,
        "ffzyapi.com": 100.0,
        "ikunzy.com": 95.0,
        "dbzy.tv": 90.0,
        "360zy.com": 80.0,
        "jszyapi.com": 75.0,
        "iqiyizyapi.com": -80.0,
    }

    def _score_item(item: SearchItem) -> float:
        score = 0.0
        t = item.title.strip().lower()
        k = keyword.lower()
        if t == k:
            score += 300.0
        elif t.startswith(k):
            score += 200.0
        elif k in t:
            score += 100.0
        else:
            score += 30.0

        score += reliable_source_scores.get(item.source_key, 10.0)
        if item.cover:
            score += 15.0
        return score

    all_results.sort(key=_score_item, reverse=True)

    # Save into memory cache
    _search_cache[cache_key] = (now, all_results)

    return ApiResponse(
        code=0,
        message=f"found {len(all_results)} results across {len(target_sources)} sources",
        data=all_results[:limit]
    )
