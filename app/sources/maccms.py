import logging
from typing import List, Optional, Dict, Any
import httpx

from app.models.media import SearchItem, MediaDetail, PlayRoute, Episode, MediaType
from app.config import settings

logger = logging.getLogger(__name__)

class MacCMSDriver:
    """
    Driver for AppleCMS (MacCMS v10) standard VOD JSON API.
    """
    
    @staticmethod
    def parse_play_routes(vod_play_from: str, vod_play_url: str) -> List[PlayRoute]:
        """
        Parses AppleCMS play sources and episode URLs.
        Format:
        vod_play_from: "source1$$$source2"
        vod_play_url: "ep1$url1#ep2$url2$$$ep1$url3#ep2$url4"
        """
        routes: List[PlayRoute] = []
        if not vod_play_url:
            return routes
            
        from_list = [f.strip() for f in (vod_play_from or "默认线路").split("$$$") if f.strip()]
        url_blocks = vod_play_url.split("$$$")
        
        for i, block in enumerate(url_blocks):
            route_name = from_list[i] if i < len(from_list) else f"线路 {i+1}"
            episodes: List[Episode] = []
            
            raw_episodes = block.split("#")
            for raw_ep in raw_episodes:
                raw_ep = raw_ep.strip()
                if not raw_ep:
                    continue
                if "$" in raw_ep:
                    parts = raw_ep.split("$", 1)
                    ep_name, ep_url = parts[0].strip(), parts[1].strip()
                else:
                    ep_name = f"第 {len(episodes) + 1} 集"
                    ep_url = raw_ep.strip()
                
                if ep_url:
                    episodes.append(Episode(name=ep_name, url=ep_url))
            
            if episodes:
                routes.append(PlayRoute(name=route_name, episodes=episodes))
                
        return routes

    @classmethod
    async def search(
        cls,
        client: httpx.AsyncClient,
        site_key: str,
        site_name: str,
        api_url: str,
        keyword: str
    ) -> List[SearchItem]:
        """
        Searches for media by keyword.
        """
        items: List[SearchItem] = []
        try:
            params = {
                "ac": "detail",
                "wd": keyword
            }
            resp = await client.get(api_url, params=params, timeout=settings.UPSTREAM_TIMEOUT)
            if resp.status_code != 200:
                logger.warning(f"[{site_name}] search failed with HTTP {resp.status_code}")
                return items
                
            data = resp.json()
            vod_list = data.get("list", [])
            for vod in vod_list:
                vod_id = str(vod.get("vod_id", ""))
                vod_name = vod.get("vod_name", "").strip()
                if not vod_id or not vod_name:
                    continue
                
                # Determine media type roughly
                type_name = vod.get("type_name", "")
                m_type = MediaType.ANIME if ("动漫" in type_name or "番剧" in type_name) else MediaType.VIDEO
                
                item = SearchItem(
                    id=f"maccms:{site_key}:{vod_id}",
                    title=vod_name,
                    cover=vod.get("vod_pic"),
                    source_key=site_key,
                    source_name=site_name,
                    remarks=vod.get("vod_remarks"),
                    type_name=type_name,
                    year=str(vod.get("vod_year", "")) if vod.get("vod_year") else None,
                    area=vod.get("vod_area"),
                    media_type=m_type
                )
                items.append(item)
        except Exception as e:
            logger.debug(f"[{site_name}] search error: {e}")
            
        return items

    @classmethod
    async def detail(
        cls,
        client: httpx.AsyncClient,
        site_key: str,
        site_name: str,
        api_url: str,
        vod_id: str
    ) -> Optional[MediaDetail]:
        """
        Fetches full details and episodes for a given vod_id.
        """
        try:
            params = {
                "ac": "detail",
                "ids": vod_id
            }
            resp = await client.get(api_url, params=params, timeout=settings.UPSTREAM_TIMEOUT)
            if resp.status_code != 200:
                return None
                
            data = resp.json()
            vod_list = data.get("list", [])
            if not vod_list:
                return None
                
            vod = vod_list[0]
            routes = cls.parse_play_routes(
                vod.get("vod_play_from", ""),
                vod.get("vod_play_url", "")
            )
            
            type_name = vod.get("type_name", "")
            m_type = MediaType.ANIME if ("动漫" in type_name or "番剧" in type_name) else MediaType.VIDEO

            return MediaDetail(
                id=f"maccms:{site_key}:{vod_id}",
                title=vod.get("vod_name", "").strip(),
                cover=vod.get("vod_pic"),
                source_key=site_key,
                source_name=site_name,
                remarks=vod.get("vod_remarks"),
                type_name=type_name,
                year=str(vod.get("vod_year", "")) if vod.get("vod_year") else None,
                area=vod.get("vod_area"),
                media_type=m_type,
                description=vod.get("vod_content", "").strip(),
                actors=vod.get("vod_actor"),
                directors=vod.get("vod_director"),
                routes=routes
            )
        except Exception as e:
            logger.error(f"[{site_name}] detail error: {e}")
            return None
