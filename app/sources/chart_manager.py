import re
import time
import logging
from typing import List, Dict, Tuple, Optional
import httpx
from app.models.chart import ChartCategory, ChartItem

logger = logging.getLogger(__name__)

# Categories definitions
CATEGORIES: List[ChartCategory] = [
    ChartCategory(id="movie_top250", name="豆瓣Top250", description="豆瓣影史经典神作排行榜", type="movie"),
    ChartCategory(id="movie_hot", name="热门电影", description="近期影院与网络热门大片", type="movie"),
    ChartCategory(id="movie_high_score", name="高分电影", description="豆瓣高口碑电影精选", type="movie"),
    ChartCategory(id="tv_hot", name="热门剧集", description="全网当下最火爆连续剧", type="tv"),
    ChartCategory(id="tv_domestic", name="国产热播", description="国内主流热播电视剧", type="tv"),
    ChartCategory(id="tv_us", name="欧美剧集", description="高分美剧与英剧精选", type="tv"),
    ChartCategory(id="tv_kr", name="热门韩剧", description="最新高口碑韩国电视剧", type="tv"),
    ChartCategory(id="tv_jp", name="热门日剧", description="精选经典与新番日本电视剧", type="tv"),
    ChartCategory(id="tv_anime", name="日本动漫", description="豆瓣高分与热门动漫番剧", type="tv"),
    ChartCategory(id="tv_variety", name="热门综艺", description="国内外爆款综艺与真人秀", type="tv"),
]

# Mapping for Douban web API
DOUBAN_TAG_MAP = {
    "movie_hot": ("movie", "热门"),
    "movie_high_score": ("movie", "豆瓣高分"),
    "movie_latest": ("movie", "最新"),
    "tv_hot": ("tv", "热门"),
    "tv_domestic": ("tv", "国产剧"),
    "tv_us": ("tv", "美剧"),
    "tv_kr": ("tv", "韩剧"),
    "tv_jp": ("tv", "日剧"),
    "tv_anime": ("tv", "日本动画"),
    "tv_variety": ("tv", "综艺"),
}

class ChartManager:
    _instance: Optional["ChartManager"] = None

    def __init__(self):
        # Cache format: { cache_key: (timestamp, List[ChartItem]) }
        self._cache: Dict[str, Tuple[float, List[ChartItem]]] = {}
        self._cache_ttl = 3600  # 1 hour

    @classmethod
    def get_instance(cls) -> "ChartManager":
        if cls._instance is None:
            cls._instance = ChartManager()
        return cls._instance

    def get_categories(self) -> List[ChartCategory]:
        return CATEGORIES

    async def get_chart_items(self, category_id: str, page: int = 1, limit: int = 20) -> List[ChartItem]:
        cache_key = f"{category_id}:{page}:{limit}"
        now = time.time()

        if cache_key in self._cache:
            ts, items = self._cache[cache_key]
            if now - ts < self._cache_ttl:
                return items

        items: List[ChartItem] = []
        try:
            if category_id == "movie_top250":
                items = await self._fetch_top250(page, limit)
            elif category_id in DOUBAN_TAG_MAP:
                media_type, tag = DOUBAN_TAG_MAP[category_id]
                items = await self._fetch_douban_tag(media_type, tag, category_id, page, limit)
            else:
                items = []

            if items:
                self._cache[cache_key] = (now, items)
        except Exception as e:
            logger.error(f"Error fetching chart items for {category_id}: {e}")

        return items

    async def _fetch_top250(self, page: int, limit: int) -> List[ChartItem]:
        start = (page - 1) * 25
        url = f"https://movie.douban.com/top250?start={start}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://movie.douban.com/",
            "X-Forwarded-For": "116.25.146.177",
        }

        async with httpx.AsyncClient(headers=headers, timeout=12.0) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.warning(f"Douban top250 returned status {resp.status_code}")
                return []

            html = resp.text
            matches = re.findall(
                r'<div class="item">.*?<img.*?src="([^"]+)".*?<span class="title">([^<]+)</span>.*?<span class="rating_num"[^>]*>([^<]+)</span>',
                html,
                re.DOTALL
            )

            results: List[ChartItem] = []
            for cover, title, rate in matches:
                clean_title = title.strip()
                results.append(ChartItem(
                    id=f"top250_{clean_title}",
                    title=clean_title,
                    rate=rate.strip(),
                    cover=cover.strip(),
                    category_id="movie_top250",
                    url=None,
                ))
            return results[:limit]

    async def _fetch_douban_tag(self, media_type: str, tag: str, category_id: str, page: int, limit: int) -> List[ChartItem]:
        start = (page - 1) * limit
        url = "https://movie.douban.com/j/search_subjects"
        params = {
            "type": media_type,
            "tag": tag,
            "page_limit": limit,
            "page_start": start,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://movie.douban.com/",
            "X-Forwarded-For": "116.25.146.177",
        }

        async with httpx.AsyncClient(headers=headers, timeout=12.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                logger.warning(f"Douban search_subjects {tag} returned {resp.status_code}")
                return []

            data = resp.json()
            subjects = data.get("subjects", [])
            results: List[ChartItem] = []
            for s in subjects:
                results.append(ChartItem(
                    id=f"douban_{s.get('id', s.get('title'))}",
                    title=s.get("title", "").strip(),
                    rate=str(s.get("rate", "")) if s.get("rate") else None,
                    cover=s.get("cover"),
                    url=s.get("url"),
                    episodes_info=s.get("episodes_info"),
                    category_id=category_id,
                ))
            return results
