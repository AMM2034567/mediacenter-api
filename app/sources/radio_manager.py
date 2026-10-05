import logging
import random
import time
from typing import List, Optional
import httpx

from app.models.live import RadioStation, LiveChannel, LiveStreamLine
from app.models.media import MediaType

logger = logging.getLogger(__name__)

# Official Radio-Browser public API servers with load balancing
RADIO_BROWSER_SERVERS = [
    "https://de1.api.radio-browser.info",
    "https://nl1.api.radio-browser.info",
    "https://at1.api.radio-browser.info",
]

# 高可用内置经典广播电台（CNR中国之声、音乐之声、经济之声、经典音乐、北京交通广播、广东音乐之声等）
BUILTIN_RADIO_STATIONS = [
    RadioStation(
        station_uuid="builtin-cnr-1",
        name="CNR 中国之声",
        url="http://ngcdn001.cnr.cn/live/zgzs/index.m3u8",
        favicon="https://bkimg.cdn.bcebos.com/pic/0824ab18972bd40735fa52c6f1d78a510fb309fc",
        country="China",
        countrycode="CN",
        state="北京",
        tags="新闻,国家广播,央广",
        codec="AAC",
        bitrate=128,
        votes=9999,
        clickcount=99999
    ),
    RadioStation(
        station_uuid="builtin-cnr-2",
        name="CNR 经济之声",
        url="http://ngcdn002.cnr.cn/live/jjzs/index.m3u8",
        favicon="https://bkimg.cdn.bcebos.com/pic/0824ab18972bd40735fa52c6f1d78a510fb309fc",
        country="China",
        countrycode="CN",
        state="北京",
        tags="财经,经济,央广",
        codec="AAC",
        bitrate=128,
        votes=8888,
        clickcount=66666
    ),
    RadioStation(
        station_uuid="builtin-cnr-3",
        name="CNR 音乐之声 (MusicRadio)",
        url="http://ngcdn003.cnr.cn/live/yyzs/index.m3u8",
        favicon="https://bkimg.cdn.bcebos.com/pic/0824ab18972bd40735fa52c6f1d78a510fb309fc",
        country="China",
        countrycode="CN",
        state="北京",
        tags="流行音乐,华语榜单,车载流行",
        codec="AAC",
        bitrate=128,
        votes=15000,
        clickcount=120000
    ),
    RadioStation(
        station_uuid="builtin-cnr-4",
        name="CNR 经典音乐广播",
        url="http://ngcdn004.cnr.cn/live/jdyygb/index.m3u8",
        favicon="https://bkimg.cdn.bcebos.com/pic/0824ab18972bd40735fa52c6f1d78a510fb309fc",
        country="China",
        countrycode="CN",
        state="北京",
        tags="经典老歌,怀旧金曲,轻音乐",
        codec="AAC",
        bitrate=128,
        votes=11000,
        clickcount=88888
    ),
    RadioStation(
        station_uuid="builtin-cnr-5",
        name="CNR 中华之声",
        url="http://ngcdn005.cnr.cn/live/zhzs/index.m3u8",
        favicon="https://bkimg.cdn.bcebos.com/pic/0824ab18972bd40735fa52c6f1d78a510fb309fc",
        country="China",
        countrycode="CN",
        state="北京",
        tags="综合文化,海峡之声",
        codec="AAC",
        bitrate=128,
        votes=5000,
        clickcount=32000
    ),
    RadioStation(
        station_uuid="builtin-cnr-7",
        name="CRI 环球资讯广播",
        url="http://ngcdn011.cnr.cn/live/hqzxgb/index.m3u8",
        favicon="https://bkimg.cdn.bcebos.com/pic/0824ab18972bd40735fa52c6f1d78a510fb309fc",
        country="China",
        countrycode="CN",
        state="北京",
        tags="国际新闻,资讯深度",
        codec="AAC",
        bitrate=128,
        votes=9500,
        clickcount=76000
    ),
    RadioStation(
        station_uuid="builtin-traffic-bj",
        name="北京交通广播 FM103.9",
        url="http://listen.rbc.cn/1039.m3u8",
        favicon="https://www.rbc.cn/favicon.ico",
        country="China",
        countrycode="CN",
        state="北京",
        tags="路况信息,交通广播,车载必听",
        codec="AAC",
        bitrate=128,
        votes=12000,
        clickcount=95000
    ),
    RadioStation(
        station_uuid="builtin-music-gd",
        name="广东音乐之声 FM99.3",
        url="https://lhttp.qingting.fm/live/1083/64k.mp3",
        favicon="https://www.qingting.fm/favicon.ico",
        country="China",
        countrycode="CN",
        state="广东",
        tags="粤语流行,经典金曲,音乐",
        codec="MP3",
        bitrate=64,
        votes=8600,
        clickcount=65000
    )
]

class RadioManager:
    _instance: Optional["RadioManager"] = None

    def __init__(self):
        self._cache_stations: List[RadioStation] = list(BUILTIN_RADIO_STATIONS)
        self._last_fetched: float = 0
        self._user_agent = "MediaCenterApp/1.0 (Car Center Media Player)"

    @classmethod
    def get_instance(cls) -> "RadioManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_base_url(self) -> str:
        return random.choice(RADIO_BROWSER_SERVERS)

    async def get_top_stations(self, limit: int = 60, country_code: str = "CN") -> List[RadioStation]:
        """从 radio-browser.info 获取热门电台，优先合并内置高可用源"""
        if self._cache_stations and (time.time() - self._last_fetched < 1800) and len(self._cache_stations) > len(BUILTIN_RADIO_STATIONS):
            return self._cache_stations[:limit]

        headers = {"User-Agent": self._user_agent}
        
        # 遍历所有可用节点，避免单节点 DNS 解析失败
        servers = list(RADIO_BROWSER_SERVERS)
        random.shuffle(servers)

        for base_url in servers:
            api_url = f"{base_url}/json/stations/search?countrycode={country_code}&order=votes&reverse=true&limit={limit}"
            try:
                async with httpx.AsyncClient(headers=headers, timeout=6.0, follow_redirects=True) as client:
                    resp = await client.get(api_url)
                    if resp.status_code == 200:
                        data = resp.json()
                        seen_urls = {b.url for b in BUILTIN_RADIO_STATIONS}
                        results: List[RadioStation] = list(BUILTIN_RADIO_STATIONS)

                        for item in data:
                            stream_url = item.get("url_resolved") or item.get("url", "")
                            if not stream_url or stream_url in seen_urls:
                                continue
                            seen_urls.add(stream_url)
                            
                            st = RadioStation(
                                station_uuid=item.get("stationuuid") or f"rb-{random.randint(1000, 9999)}",
                                name=item.get("name", "未命名电台").strip(),
                                url=stream_url,
                                favicon=item.get("favicon") or None,
                                country=item.get("country"),
                                countrycode=item.get("countrycode"),
                                state=item.get("state"),
                                tags=item.get("tags"),
                                codec=item.get("codec"),
                                bitrate=item.get("bitrate"),
                                votes=item.get("votes", 0),
                                clickcount=item.get("clickcount", 0),
                            )
                            results.append(st)

                        self._cache_stations = results
                        self._last_fetched = time.time()
                        logger.info(f"Loaded {len(results)} radio stations from Radio-Browser ({base_url}) + Builtin!")
                        return results[:limit]
            except Exception as e:
                logger.debug(f"Node {base_url} failed: {e}, trying next node...")

        logger.warning("All Radio-Browser nodes timed out, returning builtin stations.")
        return BUILTIN_RADIO_STATIONS[:limit]

    async def search_stations(self, keyword: str, limit: int = 40) -> List[RadioStation]:
        """关键词搜索电台"""
        keyword = keyword.strip()
        if not keyword:
            return await self.get_top_stations(limit=limit)

        local_matches = [
            s for s in BUILTIN_RADIO_STATIONS 
            if keyword.lower() in s.name.lower() or (s.tags and keyword.lower() in s.tags.lower())
        ]

        headers = {"User-Agent": self._user_agent}
        servers = list(RADIO_BROWSER_SERVERS)
        random.shuffle(servers)

        for base_url in servers:
            api_url = f"{base_url}/json/stations/search?name={keyword}&limit={limit}"
            try:
                async with httpx.AsyncClient(headers=headers, timeout=6.0, follow_redirects=True) as client:
                    resp = await client.get(api_url)
                    if resp.status_code == 200:
                        data = resp.json()
                        seen_urls = {m.url for m in local_matches}
                        results: List[RadioStation] = list(local_matches)

                        for item in data:
                            stream_url = item.get("url_resolved") or item.get("url", "")
                            if not stream_url or stream_url in seen_urls:
                                continue
                            seen_urls.add(stream_url)
                            results.append(RadioStation(
                                station_uuid=item.get("stationuuid") or f"rb-{random.randint(1000, 9999)}",
                                name=item.get("name", "未命名电台").strip(),
                                url=stream_url,
                                favicon=item.get("favicon") or None,
                                country=item.get("country"),
                                countrycode=item.get("countrycode"),
                                state=item.get("state"),
                                tags=item.get("tags"),
                                codec=item.get("codec"),
                                bitrate=item.get("bitrate"),
                                votes=item.get("votes", 0),
                                clickcount=item.get("clickcount", 0),
                            ))
                        return results[:limit]
            except Exception as e:
                logger.debug(f"Search node {base_url} failed: {e}")

        return local_matches

    def to_live_channels(self, stations: List[RadioStation]) -> List[LiveChannel]:
        """将 RadioStation 统一转换为标准 LiveChannel，让客户端播放器可无缝播放"""
        channels: List[LiveChannel] = []
        for s in stations:
            channel_id = f"radio:{s.station_uuid}"
            channels.append(LiveChannel(
                id=channel_id,
                name=s.name,
                raw_name=s.name,
                group="广播电台",
                logo=s.favicon,
                tvg_id=s.station_uuid,
                media_type=MediaType.LIVE,
                is_radio=True,
                lines=[LiveStreamLine(name=f"默认线路 ({s.codec or 'AUDIO'})", url=s.url)],
                current_url=s.url
            ))
        return channels
