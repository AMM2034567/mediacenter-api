import logging
from typing import Dict, List, Optional
import httpx

from app.models.media import SourceInfo
from app.core.base58 import decode_base58_json
from app.config import settings

logger = logging.getLogger(__name__)

# Fallback default sources in case remote GitHub is temporarily unreachable
FALLBACK_SOURCES: List[SourceInfo] = [
    SourceInfo(key="cj.lzcaiji.com", name="🎬量子资源", api="https://cj.lzcaiji.com/api.php/provide/vod"),
    SourceInfo(key="bfzy.tv", name="🎬暴风资源", api="https://bfzyapi.com/api.php/provide/vod"),
    SourceInfo(key="ikunzy.com", name="🎬iKun资源", api="https://ikunzyapi.com/api.php/provide/vod"),
    SourceInfo(key="ffzyapi.com", name="🎬非凡资源", api="https://api.ffzyapi.com/api.php/provide/vod"),
    SourceInfo(key="wolongzyw.com", name="🎬卧龙资源", api="https://wolongzyw.com/api.php/provide/vod"),
]

class SourceManager:
    """
    Manages active media sources.
    Loads and updates subscription configurations from remote Base58 URL.
    """
    _instance: Optional["SourceManager"] = None
    
    def __init__(self):
        self._sources: Dict[str, SourceInfo] = {}
        # Prepopulate with fallback sources
        for s in FALLBACK_SOURCES:
            self._sources[s.key] = s

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
                    logger.info(f"Successfully loaded {len(self._sources)} sources from remote subscription!")
                else:
                    logger.warning("Decoded remote config had no api_site entries, keeping existing sources.")
                    
            except Exception as e:
                logger.error(f"Error decoding or updating remote source config: {e}")
                
        return len(self._sources)
