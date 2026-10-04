import logging
import time
from typing import Dict, List, Optional
import httpx

from app.models.media import SourceInfo, AnimeSourceInfo
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

# Dedicated Anime Sources parsed from https://sub.creamycake.org/v1/css1.json
FALLBACK_ANIME_SOURCES: List[AnimeSourceInfo] = [
    AnimeSourceInfo(name="稀饭动漫", icon_url="https://dm1.xfdm.pro/upload/site/20240308-1/813e41f81d6f85bfd7a44bf8a813f9e5.png", search_url="https://dm1.xfdm.pro/search.html?wd={keyword}", tier=0),
    AnimeSourceInfo(name="girigiri愛動漫", icon_url="https://girigirilove.com/app/app_files/anime.girigirilove.com_.png", search_url="https://ani.girigirilove.com/search/-------------/?wd={keyword}", tier=0),
    AnimeSourceInfo(name="嘀嗒影视", description="直连，来自嘀嗒影视", icon_url="https://www.didahd.pro/template/mytheme/statics/img/favicon.ico", search_url="https://www.didahd.pro/search/-------------.html?wd={keyword}&submit=", tier=1),
    AnimeSourceInfo(name="叽哔动漫", description="直连，来自叽哔动漫", icon_url="https://www.jibi.cc/upload/mxprocms/20240530-1/811f55cb787194c59e3f6d1d8724571c.jpg", search_url="https://www.jibi.cc/index.php/vod/search.html?wd={keyword}", tier=3),
    AnimeSourceInfo(name="E-ACG", description="直连，来自E-ACG", icon_url="https://i.loli.net/2019/12/09/17hvXK2LemTtgfs.png", search_url="https://www.eacg1.com/vodsearch/-------------.html?wd={keyword}", tier=3),
    AnimeSourceInfo(name="森之屋动漫", description="直连，来自森之屋动漫", icon_url="https://senfun.in/static/senfun/mxtheme/images/favicon.png", search_url="https://senfun.in/search.html?wd={keyword}", tier=3),
    AnimeSourceInfo(name="风车影视", description="直连，来自风车影视", icon_url="https://www.dongmandaquan.vip/template/a_0011/images/favicon.ico?v=20221112", search_url="https://www.dongmandaquan.vip/vodsearch/-------------.html?wd={keyword}", tier=3),
    AnimeSourceInfo(name="去看吧", description="直连，来自去看吧", icon_url="https://11kt.net/klogo.png", search_url="https://11kt.net/index.php/vod/search.html?wd={keyword}", tier=3),
    AnimeSourceInfo(name="海星动漫", description="直连", icon_url="https://www.haixingdmx.com/hdst/hx_pic/favicon.ico", search_url="https://www.haixingdmx.com/s_all?ex=1&kw={keyword}", tier=4),
    AnimeSourceInfo(name="樱花动漫", icon_url="https://www.yinghua2.com/statics/img/favicon.ico", search_url="https://www.yinghua2.com/index.php/vod/search.html?wd={keyword}", tier=4),
    AnimeSourceInfo(name="嘀哩嘀哩", description="直连，来自嘀哩嘀哩", icon_url="https://bkimg.cdn.bcebos.com/pic/c2fdfc039245d688d43f36eaa0986a1ed21b0ef48e71", search_url="https://dilidili.io/search?q={keyword}", tier=4),
    AnimeSourceInfo(name="新优酷", description="直连，来自新优酷", icon_url="https://www.youknow.tv/upload/mxprocms/20240119-1/55e70266f81055026bb40dee6a603812.png", search_url="https://www.youknow.tv/search/-------------/?wd={keyword}", tier=4),
    AnimeSourceInfo(name="番茄动漫", icon_url="https://www.fqdm.cc/upload/mxprocms/20240530-1/3d17fab3cb763e6ad7031974bf87f322.jpg", search_url="https://www.fqdm.cc/index.php/vod/search.html?wd={keyword}", tier=4),
    AnimeSourceInfo(name="hanime1_1080p", description="动漫专线", search_url="https://hanime1.me/search?query={keyword}", tier=4),
    AnimeSourceInfo(name="hanime1_720p", description="备用专线", search_url="https://hanime1.me/search?query={keyword}", tier=4),
    AnimeSourceInfo(name="wedm", search_url="https://www.vdm5.com/search_-------------.html?wd={keyword}", tier=4),
    AnimeSourceInfo(name="影视森林", icon_url="http://www.hc34567.com/static/images/logo.png", search_url="http://www.hc34567.com/hcvodsearch/{keyword}----------1---.html", tier=4),
    AnimeSourceInfo(name="热播之家", description="直连", icon_url="https://www.rebozj.pro/template/jianhei/statics/img/favicon.png", search_url="https://www.rebozj.pro/search/-------------.html?wd={keyword}&submit=", tier=4),
]


class SourceManager:
    """
    Manages active media sources.
    Loads and updates subscription configurations from remote Base58 URL.
    """
    _instance: Optional["SourceManager"] = None
    
    def __init__(self):
        self._sources: Dict[str, SourceInfo] = {}
        self._anime_sources: List[AnimeSourceInfo] = list(FALLBACK_ANIME_SOURCES)
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

    def list_anime_sources(self) -> List[AnimeSourceInfo]:
        return self._anime_sources

    def get_source(self, key: str) -> Optional[SourceInfo]:
        return self._sources.get(key)

    async def reload_anime_sources(self, url: Optional[str] = None) -> int:
        """Fetches and updates anime sources from creamy cake subscription."""
        target_url = url or settings.ANIME_SOURCE_URL
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(target_url)
                if resp.status_code == 200:
                    data = resp.json()
                    media_sources = data.get("exportedMediaSourceDataList", {}).get("mediaSources", [])
                    new_anime_sources: List[AnimeSourceInfo] = []
                    for s in media_sources:
                        args = s.get("arguments", {})
                        new_anime_sources.append(AnimeSourceInfo(
                            name=args.get("name", "未命名源"),
                            description=args.get("description", ""),
                            icon_url=args.get("iconUrl"),
                            search_url=args.get("searchConfig", {}).get("searchUrl", ""),
                            tier=args.get("tier", 0)
                        ))
                    if new_anime_sources:
                        self._anime_sources = new_anime_sources
                        logger.info(f"Loaded {len(self._anime_sources)} anime sources from {target_url}")
        except Exception as e:
            logger.warning(f"Failed to reload anime sources: {e}")
        return len(self._anime_sources)

    async def reload_from_remote(self, url: Optional[str] = None) -> int:
        """
        Fetches the remote Base58 configuration from GitHub, decodes it,
        and updates the active sources list.
        """
        target_url = url or settings.DEFAULT_SOURCE_URL
        logger.info(f"Fetching remote source config from: {target_url}")
        
        # Also reload anime sources
        try:
            await self.reload_anime_sources()
        except Exception as e:
            logger.debug(f"Anime source reload error: {e}")

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

