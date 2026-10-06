import asyncio
import logging
import time
from typing import List, Optional, Dict
import httpx

from app.models.music import MusicSong, MusicRank

logger = logging.getLogger("music_manager")

NETEASE_RANKS = [
    {
        "id": "netease:3778678",
        "name": "热歌榜",
        "description": "全网最热门火爆的流行单曲",
        "cover": "https://p1.music.126.net/GHhuNnNg57zBJ7x6Wf1VzA==/109951165682121696.jpg?param=300y300",
        "update_frequency": "每周四更新",
        "platform": "netease",
    },
    {
        "id": "netease:19723756",
        "name": "飙升榜",
        "description": "云音乐官方根据近100天单曲播放增量推荐",
        "cover": "https://p1.music.126.net/DrRIg6CrgDfVLEph9SNh7w==/18696095720518497.jpg?param=300y300",
        "update_frequency": "每天更新",
        "platform": "netease",
    },
    {
        "id": "netease:3779629",
        "name": "新歌榜",
        "description": "最新发布的热门好听新单曲",
        "cover": "https://p1.music.126.net/N2HO1XM2tOkxAVU09UhnCw==/18979770070844786.jpg?param=300y300",
        "update_frequency": "每天更新",
        "platform": "netease",
    },
    {
        "id": "netease:2884035",
        "name": "抖音热歌榜",
        "description": "当下短视频平台最受欢迎背景音乐",
        "cover": "https://p1.music.126.net/efrbYv18f1lP5DovrI2_8w==/109951165682126487.jpg?param=300y300",
        "update_frequency": "每周五更新",
        "platform": "netease",
    },
    {
        "id": "netease:24381616",
        "name": "经典老歌榜",
        "description": "岁月沉淀的永恒金曲，百听不厌",
        "cover": "https://p1.music.126.net/13593683615467384/109951165682138982.jpg?param=300y300",
        "update_frequency": "每周更新",
        "platform": "netease",
    },
]

QQ_RANKS = [
    {
        "id": "qq:26",
        "name": "热歌榜",
        "description": "QQ音乐流行最火热金曲榜",
        "cover": "https://y.gtimg.cn/music/photo_new/T003R300x300M000000b7Jg94SbWCX.jpg",
        "update_frequency": "每日更新",
        "platform": "qq",
    },
    {
        "id": "qq:62",
        "name": "飙升榜",
        "description": "QQ音乐单曲播放飙升最快排行",
        "cover": "https://y.gtimg.cn/music/photo_new/T003R300x300M000004gA1cd3wRFzk.jpg",
        "update_frequency": "每日更新",
        "platform": "qq",
    },
    {
        "id": "qq:27",
        "name": "新歌榜",
        "description": "QQ音乐最新潮好歌速递",
        "cover": "https://y.gtimg.cn/music/photo_new/T003R300x300M000002jpxFW2W8GkV.jpg",
        "update_frequency": "每日更新",
        "platform": "qq",
    },
    {
        "id": "qq:4",
        "name": "流行指数榜",
        "description": "QQ音乐潮流热度风向标",
        "cover": "https://y.gtimg.cn/music/photo_new/T003R300x300M000001YvNdx3LaMgR.jpg",
        "update_frequency": "每日更新",
        "platform": "qq",
    },
]

DOMESTIC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; MI 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "X-Forwarded-For": "116.25.146.177",
    "X-Real-IP": "116.25.146.177",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://music.163.com/",
}

def _format_cover_url(cover: Optional[str]) -> Optional[str]:
    """统一规范化封面图片为 HTTPS 并追加高清缩略图参数，解决移动端防盗链及安全协议拦截"""
    if not cover:
        return None
    cover = cover.strip()
    if not cover:
        return None
    if cover.startswith("http://"):
        cover = "https://" + cover[7:]
    if "music.126.net" in cover and "?param=" not in cover:
        cover = f"{cover}?param=300y300"
    return cover


class MusicManager:
    _instance: Optional["MusicManager"] = None

    def __init__(self):
        self._rank_cache: Dict[str, tuple[float, List[MusicSong]]] = {}
        self._cache_ttl = 3600  # 1小时缓存

    @classmethod
    def get_instance(cls) -> "MusicManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_ranks(self, platform: Optional[str] = None) -> List[MusicRank]:
        """获取所有可用音乐榜单，支持按平台过滤 (netease / qq / all)"""
        if platform == "netease":
            raw_list = NETEASE_RANKS
        elif platform == "qq":
            raw_list = QQ_RANKS
        else:
            raw_list = NETEASE_RANKS + QQ_RANKS

        return [
            MusicRank(
                id=r["id"],
                name=r["name"],
                description=r["description"],
                cover=r["cover"],
                update_frequency=r["update_frequency"],
                platform=r["platform"],
            )
            for r in raw_list
        ]

    async def get_rank_songs(self, rank_id: str, limit: int = 100) -> List[MusicSong]:
        """获取指定榜单歌曲列表，支持网易云与 QQ 音乐原生排行榜"""
        now = time.time()
        if rank_id in self._rank_cache:
            cache_time, cached_songs = self._rank_cache[rank_id]
            if now - cache_time < self._cache_ttl:
                return cached_songs[:limit]

        # 1. 处理 QQ 音乐榜单
        if rank_id.startswith("qq:"):
            top_id_str = rank_id.replace("qq:", "")
            try:
                top_id = int(top_id_str)
            except ValueError:
                top_id = 26

            payload = {
                "detail": {
                    "module": "musicToplist.ToplistInfoServer",
                    "method": "GetDetail",
                    "param": {
                        "topId": top_id,
                        "offset": 0,
                        "num": limit,
                        "period": "",
                    },
                }
            }
            qq_headers = dict(DOMESTIC_HEADERS)
            qq_headers["Referer"] = "https://y.qq.com/"
            async with httpx.AsyncClient(headers=qq_headers, timeout=8.0) as client:
                try:
                    resp = await client.post("https://u.y.qq.com/cgi-bin/musicu.fcg", json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        song_info_list = data.get("detail", {}).get("data", {}).get("songInfoList", [])
                        songs: List[MusicSong] = []
                        for s in song_info_list:
                            mid = s.get("mid")
                            if not mid:
                                continue
                            name = s.get("title", "未知歌曲")
                            singers = [a.get("name", "") for a in s.get("singer", []) if a.get("name")]
                            artist_name = " / ".join(singers) or "群星"
                            album_obj = s.get("album", {})
                            album_name = album_obj.get("name")
                            album_mid = album_obj.get("mid")
                            cover = f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{album_mid}.jpg" if album_mid else None
                            duration = s.get("interval", 0)
                            songs.append(
                                MusicSong(
                                    id=f"qq:{mid}",
                                    name=name,
                                    artist=artist_name,
                                    album=album_name,
                                    cover=_format_cover_url(cover),
                                    duration=duration,
                                    platform="qq",
                                    mid=mid,
                                    play_url=None,
                                )
                            )
                        self._rank_cache[rank_id] = (now, songs)
                        return songs[:limit]
                except Exception as e:
                    logger.error(f"Error fetching QQ rank songs {rank_id}: {e}")
            return []

        # 2. 处理网易云榜单
        netease_id = rank_id.replace("netease:", "")
        url = f"https://music.163.com/api/playlist/detail?id={netease_id}"
        async with httpx.AsyncClient(headers=DOMESTIC_HEADERS, timeout=8.0) as client:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    tracks = data.get("result", {}).get("tracks", [])
                    songs: List[MusicSong] = []
                    for t in tracks:
                        sid = str(t.get("id"))
                        name = t.get("name", "未知歌曲")
                        artists = t.get("artists", [])
                        artist_name = " / ".join([a.get("name", "") for a in artists if a.get("name")]) or "群星"
                        album = t.get("album", {}).get("name")
                        raw_cover = t.get("album", {}).get("picUrl")
                        cover = _format_cover_url(raw_cover)
                        duration = (t.get("duration", 0) or 0) // 1000

                        songs.append(
                            MusicSong(
                                id=f"netease:{sid}",
                                name=name,
                                artist=artist_name,
                                album=album,
                                cover=cover,
                                duration=duration,
                                platform="netease",
                                play_url=None,  # 播放时动态走多级音源解析，解除 30 秒截断限制
                            )
                        )
                    self._rank_cache[rank_id] = (now, songs)
                    return songs[:limit]
            except Exception as e:
                logger.error(f"Error fetching rank songs {rank_id}: {e}")

        return []

    async def _search_netease(self, client: httpx.AsyncClient, keyword: str, limit: int = 30) -> List[MusicSong]:
        """网易云官方搜索"""
        results: List[MusicSong] = []
        try:
            search_url = f"https://music.163.com/api/search/get/web?s={keyword}&type=1&offset=0&limit={limit}"
            r_wy = await client.get(search_url)
            if r_wy.status_code == 200:
                data = r_wy.json()
                songs = data.get("result", {}).get("songs", [])
                for s in songs:
                    sid = str(s.get("id"))
                    name = s.get("name", "")
                    artists = s.get("artists", [])
                    artist_name = " / ".join([a.get("name", "") for a in artists if a.get("name")]) or "未知"
                    album = s.get("album", {}).get("name")
                    raw_cover = s.get("album", {}).get("picUrl") or s.get("album", {}).get("artist", {}).get("img1v1Url")
                    cover = _format_cover_url(raw_cover)
                    duration = (s.get("duration", 0) or 0) // 1000

                    results.append(
                        MusicSong(
                            id=f"netease:{sid}",
                            name=name,
                            artist=artist_name,
                            album=album,
                            cover=cover,
                            duration=duration,
                            platform="netease",
                            play_url=None,
                        )
                    )
        except Exception as e:
            logger.error(f"Error searching NetEase: {e}")
        return results

    async def _search_qq(self, client: httpx.AsyncClient, keyword: str, limit: int = 30) -> List[MusicSong]:
        """搜索 QQ 音乐官方源，优先使用 DoSearchForQQMusicDesktop，失败回退到 Tang 与 Smartbox"""
        qq_songs: List[MusicSong] = []
        qq_headers = dict(DOMESTIC_HEADERS)
        qq_headers["Referer"] = "https://y.qq.com/"

        # 1. 官方 DoSearchForQQMusicDesktop（精准匹配全量周杰伦、热门流行曲目）
        try:
            payload = {
                "req": {
                    "module": "music.search.SearchCgiService",
                    "method": "DoSearchForQQMusicDesktop",
                    "param": {
                        "query": keyword,
                        "page_num": 1,
                        "num_per_page": limit,
                        "search_type": 0,
                    },
                }
            }
            r = await client.post("https://u.y.qq.com/cgi-bin/musicu.fcg", json=payload, headers=qq_headers, timeout=5.0)
            if r.status_code == 200:
                body = r.json().get("req", {}).get("data", {}).get("body", {})
                slist = body.get("song", {}).get("list", [])
                for s in slist:
                    mid = s.get("mid")
                    if not mid:
                        continue
                    title = s.get("title", "")
                    singers = [a.get("name", "") for a in s.get("singer", []) if a.get("name")]
                    artist_name = " / ".join(singers) or "未知歌手"
                    album_obj = s.get("album", {})
                    album_name = album_obj.get("name")
                    album_mid = album_obj.get("mid")
                    cover = f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{album_mid}.jpg" if album_mid else None
                    duration = s.get("interval", 0)
                    qq_songs.append(
                        MusicSong(
                            id=f"qq:{mid}",
                            name=title,
                            artist=artist_name,
                            album=album_name,
                            cover=_format_cover_url(cover),
                            duration=duration,
                            platform="qq",
                            mid=mid,
                            play_url=None,
                        )
                    )
                if qq_songs:
                    return qq_songs
        except Exception as e:
            logger.warning(f"Error calling QQ DoSearchForQQMusicDesktop: {e}")

        # 2. 回退 Tang 接口
        try:
            qq_url = f"https://tang.api.s01s.cn/music_open_api.php?msg={keyword}&type=json"
            r_qq = await client.get(qq_url, timeout=3.5)
            if r_qq.status_code == 200:
                data = r_qq.json()
                if isinstance(data, list):
                    for item in data[:limit]:
                        mid = item.get("song_mid")
                        title = item.get("song_title", "")
                        singer = item.get("singer_name", "")
                        if mid and title and not any(s.id == f"qq:{mid}" for s in qq_songs):
                            qq_songs.append(
                                MusicSong(
                                    id=f"qq:{mid}",
                                    name=title,
                                    artist=singer,
                                    album="QQ音乐",
                                    platform="qq",
                                    mid=mid,
                                    cover=None,
                                    play_url=None,
                                )
                            )
                if qq_songs:
                    return qq_songs
        except Exception as e:
            logger.warning(f"Error calling QQ Tang fallback: {e}")

        # 3. 回退 Smartbox
        try:
            smartbox_url = f"https://c.y.qq.com/splcloud/fcgi-bin/smartbox_new.fcg?key={keyword}&format=json"
            r_sb = await client.get(smartbox_url, headers=qq_headers, timeout=3.5)
            if r_sb.status_code == 200:
                items = r_sb.json().get("data", {}).get("song", {}).get("itemlist", [])
                for item in items:
                    mid = item.get("mid")
                    title = item.get("name", "")
                    singer = item.get("singer", "")
                    if mid and title and not any(s.id == f"qq:{mid}" for s in qq_songs):
                        qq_songs.append(
                            MusicSong(
                                id=f"qq:{mid}",
                                name=title,
                                artist=singer,
                                album="QQ音乐",
                                platform="qq",
                                mid=mid,
                                cover=None,
                                play_url=None,
                            )
                        )
        except Exception as e:
            logger.warning(f"Error calling QQ smartbox fallback: {e}")

        return qq_songs

    async def search_songs(self, keyword: str, platform: Optional[str] = None, limit: int = 30) -> List[MusicSong]:
        """搜索歌曲，支持平台过滤 (netease / qq / all)"""
        async with httpx.AsyncClient(headers=DOMESTIC_HEADERS, timeout=6.0) as client:
            if platform == "qq":
                return await self._search_qq(client, keyword, limit)

            if platform == "netease":
                return await self._search_netease(client, keyword, limit)

            # 默认 all: 并行搜索 QQ 与网易云
            tasks = [
                self._search_qq(client, keyword, limit),
                self._search_netease(client, keyword, limit),
            ]
            qq_res, wy_res = await asyncio.gather(*tasks, return_exceptions=True)
            qq_list = qq_res if isinstance(qq_res, list) else []
            wy_list = wy_res if isinstance(wy_res, list) else []

            # 智能优先级：若查询词包含周杰伦/Jay，将 QQ 音乐独家版权歌曲置顶
            kw_lower = keyword.lower()
            if "周杰伦" in keyword or "jay" in kw_lower:
                return (qq_list + wy_list)[:limit]

            # 交叉融合结果
            combined: List[MusicSong] = []
            max_len = max(len(wy_list), len(qq_list))
            for i in range(max_len):
                if i < len(wy_list):
                    combined.append(wy_list[i])
                if i < len(qq_list):
                    combined.append(qq_list[i])
            return combined[:limit]

    async def get_song_play_url(self, song_id: str, title: str = "", artist: str = "") -> Optional[str]:
        """获取歌曲完整播放直链（多级音源回退，彻底解除 30 秒截断限制）"""
        if song_id.startswith("netease:"):
            sid = song_id.replace("netease:", "")
            async with httpx.AsyncClient(headers=DOMESTIC_HEADERS, timeout=6.0) as client:
                # 链路 1: gdstudio 解析（稳定返回 320k / 无损完整音频，不截断）
                try:
                    u = f"https://music-api.gdstudio.xyz/api.php?types=url&source=netease&id={sid}"
                    r = await client.get(u)
                    if r.status_code == 200:
                        play_url = r.json().get("url", "")
                        if play_url and play_url.startswith("http"):
                            return play_url.replace("http://", "https://")
                except Exception as e:
                    logger.warning(f"gdstudio failed for netease:{sid}: {e}")

                # 链路 2: oiapi.net 解析（备用完整音频源）
                try:
                    u = f"https://oiapi.net/api/Music_163?id={sid}&key=oiapi-ef6133b7-ac2f-dc7d-878c-d3e207a82575"
                    r = await client.get(u)
                    if r.status_code == 200:
                        data = r.json().get("data", [])
                        if data and data[0].get("url"):
                            play_url = data[0]["url"]
                            if play_url.startswith("http"):
                                return play_url.replace("http://", "https://")
                except Exception as e:
                    logger.warning(f"oiapi failed for netease:{sid}: {e}")

                # 链路 3: 跨平台 QQ 音乐同名回退（针对网易云 VIP/独家全网下架歌曲，如周杰伦全系）
                try:
                    song_title = title
                    song_artist = artist
                    if not song_title:
                        # 查歌曲名
                        r_det = await client.get(f"https://music.163.com/api/song/detail?ids=[{sid}]", timeout=3.0)
                        if r_det.status_code == 200:
                            s_list = r_det.json().get("songs", [])
                            if s_list:
                                song_title = s_list[0].get("name", "")
                                song_artist = " ".join([a.get("name", "") for a in s_list[0].get("artists", [])])

                    if song_title:
                        kw = f"{song_title} {song_artist}".strip()
                        qq_headers = dict(DOMESTIC_HEADERS)
                        qq_headers["Referer"] = "https://y.qq.com/"
                        r_sb = await client.get(
                            f"https://c.y.qq.com/splcloud/fcgi-bin/smartbox_new.fcg?key={kw}&format=json",
                            headers=qq_headers,
                            timeout=3.5
                        )
                        if r_sb.status_code == 200:
                            items = r_sb.json().get("data", {}).get("song", {}).get("itemlist", [])
                            if items:
                                mid = items[0].get("mid")
                                if mid:
                                    qq_url = await self._resolve_qq_url(client, mid)
                                    if qq_url:
                                        logger.info(f"Cross-resolved netease:{sid} ({kw}) to QQ:{mid}")
                                        return qq_url
                except Exception as e:
                    logger.warning(f"Cross-source fallback failed for netease:{sid}: {e}")

                # 链路 4: 网易云官方 outer 链接兜底
                return f"https://music.163.com/song/media/outer/url?id={sid}.mp3"

        if song_id.startswith("qq:"):
            mid = song_id.replace("qq:", "")
            async with httpx.AsyncClient(headers=DOMESTIC_HEADERS, timeout=6.0) as client:
                qq_url = await self._resolve_qq_url(client, mid, title=title)
                if qq_url:
                    return qq_url

        return None

    async def _resolve_qq_url(self, client: httpx.AsyncClient, mid: str, title: str = "") -> Optional[str]:
        """内部方法：解析 QQ 音乐直链（迅回思 -> Tang -> vkeys -> xinghai）"""
        # 1. 优先使用迅回思高保真直链接口
        try:
            url = f"https://api.xunhuisi.store/API/QQMusic/Song.php?mid={mid}&type=json"
            r = await client.get(url, timeout=5.0)
            if r.status_code == 200:
                d = r.json()
                m_url = d.get("music_url")
                if m_url and m_url.startswith("http"):
                    return m_url
        except Exception as e:
            logger.warning(f"xunhuisi failed for qq:{mid}: {e}")

        # 2. 备用 Tang 接口
        try:
            msg = title if title else "music"
            url = f"https://tang.api.s01s.cn/music_open_api.php?msg={msg}&type=json&mid={mid}"
            r = await client.get(url, timeout=4.5)
            if r.status_code == 200:
                d = r.json()
                if isinstance(d, dict):
                    p_url = d.get("song_play_url") or d.get("song_play_url_sq") or d.get("song_play_url_standard")
                    if p_url and p_url.startswith("http"):
                        return p_url
        except Exception as e:
            logger.warning(f"tang failed for qq:{mid}: {e}")

        # 3. 备用 vkeys 接口
        try:
            url = f"https://api.vkeys.cn/v2/music/tencent/geturl?mid={mid}"
            r = await client.get(url, timeout=4.0)
            if r.status_code == 200:
                data = r.json()
                play_url = data.get("data", {}).get("url")
                if play_url and play_url.startswith("http"):
                    return play_url
        except Exception as e:
            logger.warning(f"vkeys failed for qq:{mid}: {e}")

        # 4. 备用星海后端
        try:
            url = f"https://yy.zddyr.top/lx/api/?source=qq&songmid={mid}&quality=320k"
            r = await client.get(url, timeout=4.0)
            if r.status_code == 200:
                data = r.json()
                play_url = data.get("url")
                if play_url and play_url.startswith("http"):
                    return play_url
        except Exception as e:
            logger.warning(f"xinghai failed for qq:{mid}: {e}")

        return None

    async def get_song_detail(self, song_id: str) -> Optional[MusicSong]:
        """获取歌曲完整信息（包含高清封面、真实完整播放直链与歌词）"""
        if song_id.startswith("netease:"):
            sid = song_id.replace("netease:", "")
            lrc = await self.get_song_lrc(song_id)

            cover = None
            name = "未知歌曲"
            artist = "未知歌手"
            album = None
            duration = 0

            async with httpx.AsyncClient(headers=DOMESTIC_HEADERS, timeout=5.0) as client:
                try:
                    r = await client.get(f"https://music.163.com/api/song/detail?ids=[{sid}]")
                    if r.status_code == 200:
                        songs = r.json().get("songs", [])
                        if songs:
                            s = songs[0]
                            name = s.get("name", name)
                            artist = " / ".join([a.get("name", "") for a in s.get("artists", [])]) or artist
                            album = s.get("album", {}).get("name")
                            raw_cover = s.get("album", {}).get("picUrl")
                            cover = _format_cover_url(raw_cover)
                            duration = (s.get("duration", 0) or 0) // 1000
                except Exception:
                    pass

            play_url = await self.get_song_play_url(song_id, title=name, artist=artist)

            return MusicSong(
                id=song_id,
                name=name,
                artist=artist,
                album=album,
                cover=cover,
                duration=duration,
                platform="netease",
                play_url=play_url,
                lrc=lrc,
            )

        if song_id.startswith("qq:"):
            mid = song_id.replace("qq:", "")
            async with httpx.AsyncClient(headers=DOMESTIC_HEADERS, timeout=6.0) as client:
                # 1. 优先从迅回思获取全量详情（含封面、直链、歌词）
                try:
                    url = f"https://api.xunhuisi.store/API/QQMusic/Song.php?mid={mid}&type=json"
                    r = await client.get(url, timeout=5.0)
                    if r.status_code == 200:
                        d = r.json()
                        raw_cover = d.get("cover")
                        cover = _format_cover_url(raw_cover)
                        return MusicSong(
                            id=song_id,
                            name=d.get("title", "未知"),
                            artist=d.get("singer", "未知"),
                            album="QQ音乐",
                            cover=cover,
                            platform="qq",
                            mid=mid,
                            play_url=d.get("music_url"),
                            lrc=d.get("lyric"),
                        )
                except Exception as e:
                    logger.warning(f"Error fetching QQ song detail from xunhuisi: {e}")

                # 2. 备用从 vkeys 获取
                try:
                    url = f"https://api.vkeys.cn/v2/music/tencent/geturl?mid={mid}"
                    r = await client.get(url, timeout=5.0)
                    if r.status_code == 200:
                        d = r.json().get("data", {})
                        lrc = await self.get_song_lrc(song_id)
                        raw_cover = d.get("cover")
                        cover = _format_cover_url(raw_cover)
                        return MusicSong(
                            id=song_id,
                            name=d.get("song", "未知"),
                            artist=d.get("singer", "未知"),
                            album=d.get("album"),
                            cover=cover,
                            platform="qq",
                            mid=mid,
                            play_url=d.get("url"),
                            lrc=lrc,
                        )
                except Exception as e:
                    logger.error(f"Error fetching QQ song detail from vkeys: {e}")

        return None

    async def get_song_lrc(self, song_id: str) -> Optional[str]:
        """获取同步 LRC 歌词"""
        async with httpx.AsyncClient(headers=DOMESTIC_HEADERS, timeout=6.0) as client:
            if song_id.startswith("netease:"):
                sid = song_id.replace("netease:", "")
                try:
                    url = f"https://music.163.com/api/song/lyric?os=pc&id={sid}&lv=-1&kv=-1&tv=-1"
                    r = await client.get(url)
                    if r.status_code == 200:
                        return r.json().get("lrc", {}).get("lyric")
                except Exception as e:
                    logger.error(f"Error fetching NetEase lyric {sid}: {e}")

            if song_id.startswith("qq:"):
                mid = song_id.replace("qq:", "")
                # 优先迅回思
                try:
                    url = f"https://api.xunhuisi.store/API/QQMusic/Song.php?mid={mid}&type=json"
                    r = await client.get(url, timeout=4.0)
                    if r.status_code == 200:
                        d = r.json()
                        if d.get("lyric"):
                            return d.get("lyric")
                except Exception:
                    pass

                # 备用 Tang 接口
                try:
                    url = f"https://tang.api.s01s.cn/music_open_api.php?msg=歌词&type=json&mid={mid}"
                    r = await client.get(url, timeout=4.0)
                    if r.status_code == 200:
                        d = r.json()
                        if isinstance(d, dict):
                            return d.get("song_lyric") or d.get("lyric")
                except Exception as e:
                    logger.error(f"Error fetching QQ lyric {mid}: {e}")

        return None
