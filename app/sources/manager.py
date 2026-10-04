import logging
import time
from typing import Dict, List, Optional
import httpx

from app.models.media import SourceInfo
from app.core.base58 import decode_base58_json
from app.config import settings

logger = logging.getLogger(__name__)

# Fallback default sources: all 28 verified sources pre-embedded for instant cold-start
FALLBACK_SOURCES: List[SourceInfo] = [
    SourceInfo(key="iqiyizyapi.com", name="🎬-爱奇艺-", api="https://iqiyizyapi.com/api.php/provide/vod", detail_url="https://iqiyizyapi.com"),
    SourceInfo(key="dbzy.tv", name="🎬豆瓣资源", api="https://caiji.dbzy5.com/api.php/provide/vod", detail_url="https://dbzy.tv"),
    SourceInfo(key="mtzy.me", name="🎬茅台资源", api="https://caiji.maotaizy.cc/api.php/provide/vod", detail_url="https://mtzy.me"),
    SourceInfo(key="wolongzyw.com", name="🎬卧龙资源", api="https://wolongzyw.com/api.php/provide/vod", detail_url="https://wolongzyw.com"),
    SourceInfo(key="ikunzy.com", name="🎬iKun资源", api="https://ikunzyapi.com/api.php/provide/vod", detail_url="https://ikunzy.com"),
    SourceInfo(key="dyttzyapi.com", name="🎬电影天堂", api="http://caiji.dyttzyapi.com/api.php/provide/vod", detail_url="http://caiji.dyttzyapi.com"),
    SourceInfo(key="www.maoyanzy.com", name="🎬猫眼资源", api="https://api.maoyanapi.top/api.php/provide/vod", detail_url="https://www.maoyanzy.com"),
    SourceInfo(key="cj.lzcaiji.com", name="🎬量子资源", api="https://cj.lzcaiji.com/api.php/provide/vod", detail_url="https://cj.lzcaiji.com"),
    SourceInfo(key="360zy.com", name="🎬360 资源", api="https://360zyzz.com/api.php/provide/vod", detail_url="https://360zy.com"),
    SourceInfo(key="jszyapi.com", name="🎬极速资源", api="https://jszyapi.com/api.php/provide/vod", detail_url="https://jszyapi.com"),
    SourceInfo(key="www.moduzy.net", name="🎬魔都资源", api="https://www.mdzyapi.com/api.php/provide/vod", detail_url="https://www.moduzy.net"),
    SourceInfo(key="ffzyapi.com", name="🎬非凡资源", api="https://api.ffzyapi.com/api.php/provide/vod", detail_url="https://cj.ffzyapi.com"),
    SourceInfo(key="bfzy.tv", name="🎬暴风资源", api="https://bfzyapi.com/api.php/provide/vod", detail_url="https://bfzy.tv"),
    SourceInfo(key="zuida.xyz", name="🎬最大资源", api="https://api.zuidapi.com/api.php/provide/vod", detail_url="https://zuida.xyz"),
    SourceInfo(key="wujinzy.me", name="🎬无尽资源", api="https://api.wujinapi.me/api.php/provide/vod", detail_url="https://wujinzy.com"),
    SourceInfo(key="xinlangapi.com", name="🎬新浪资源", api="https://api.xinlangapi.com/xinlangapi.php/provide/vod", detail_url="https://xinlangapi.com"),
    SourceInfo(key="api.wwzy.tv", name="🎬旺旺资源", api="https://api.wwzy.tv/api.php/provide/vod", detail_url="https://api.wwzy.tv"),
    SourceInfo(key="www.subozy.com", name="🎬速播资源", api="https://subocaiji.com/api.php/provide/vod", detail_url="https://www.subozy.com"),
    SourceInfo(key="jinyingzy.com", name="🎬金鹰点播", api="https://jyzyapi.com/provide/vod/from/jinyingyun/at/json", detail_url="https://jinyingzy.com"),
    SourceInfo(key="p2100.net", name="🎬飘零资源", api="https://p2100.net/api.php/provide/vod", detail_url="https://p2100.net"),
    SourceInfo(key="api.ukuapi88.com", name="🎬U酷影视", api="https://api.ukuapi88.com/api.php/provide/vod", detail_url="https://www.ukuzy.com"),
    SourceInfo(key="api.guangsuapi.com", name="🎬光速资源", api="https://api.guangsuapi.com/api.php/provide/vod", detail_url="https://api.guangsuapi.com"),
    SourceInfo(key="www.hongniuzy.com", name="🎬红牛资源", api="https://www.hongniuzy2.com/api.php/provide/vod", detail_url="https://www.hongniuzy.com"),
    SourceInfo(key="caiji.moduapi.cc", name="🎬魔都动漫", api="https://caiji.moduapi.cc/api.php/provide/vod", detail_url="https://caiji.moduapi.cc"),
    SourceInfo(key="www.ryzyw.com", name="🎬如意资源", api="https://cj.rycjapi.com/api.php/provide/vod", detail_url="https://www.ryzyw.com"),
    SourceInfo(key="www.haohuazy.com", name="🎬豪华资源", api="https://hhzyapi.com/api.php/provide/vod", detail_url="https://www.haohuazy.com"),
    SourceInfo(key="bdzy1.com", name="🎬百度云zy", api="https://pz.v88.qzz.io/?url=https://api.apibdzy.com/api.php/provide/vod", detail_url="https://bdzy1.com"),
    SourceInfo(key="lovedan.net", name="🎬艾旦影视", api="https://pz.v88.qzz.io/?url=https://lovedan.net/api.php/provide/vod", detail_url="https://lovedan.net"),
]

class SourceManager:
    """
    Manages active media sources.
    Loads and updates subscription configurations from remote Base58 URL.
    """
    _instance: Optional["SourceManager"] = None
    
    def __init__(self):
        self._sources: Dict[str, SourceInfo] = {}
        self._last_updated: float = time.time()
        # Prepopulate with fallback sources
        for s in FALLBACK_SOURCES:
            self._sources[s.key] = s

    def need_refresh(self) -> bool:
        """Checks if remote sources need to be re-synchronized based on TTL (12h default)."""
        return (time.time() - self._last_updated) > settings.SOURCE_CACHE_TTL

    @classmethod
    def get_instance(cls) -> "SourceManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def list_sources(self) -> List[SourceInfo]:
        return list(self._sources.values())

    def get_source(self, key: str) -> Optional[SourceInfo]:
        return self._sources.get(key)

    async def reload_from_remote(self, url: Optional[str] = None) -> int:
        """
        Fetches the remote Base58 configuration from GitHub, decodes it,
        and updates the active sources list.
        """
        target_url = url or settings.DEFAULT_SOURCE_URL
        logger.info(f"Fetching remote source config from: {target_url}")
        
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            try:
                resp = await client.get(target_url)
                if resp.status_code != 200:
                    logger.error(f"Failed to fetch remote config: HTTP {resp.status_code}")
                    return len(self._sources)
                
                content = resp.text.strip()
                # Decode Base58
                config_data = decode_base58_json(content)
                api_sites = config_data.get("api_site", {})
                
                new_sources: Dict[str, SourceInfo] = {}
                for key, site_meta in api_sites.items():
                    api_url = site_meta.get("api", "").strip()
                    name = site_meta.get("name", key).strip()
                    detail_url = site_meta.get("detail", "").strip()
                    
                    if api_url:
                        new_sources[key] = SourceInfo(
                            key=key,
                            name=name,
                            api=api_url,
                            detail_url=detail_url,
                            is_active=True
                        )
                
                if new_sources:
                    self._sources = new_sources
                    self._last_updated = time.time()
                    logger.info(f"Successfully loaded {len(self._sources)} sources from remote subscription!")
                else:
                    logger.warning("Decoded remote config had no api_site entries, keeping existing sources.")
                    
            except Exception as e:
                logger.error(f"Error decoding or updating remote source config: {e}")
                
        return len(self._sources)
