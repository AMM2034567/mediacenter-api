import asyncio
import logging
import time
from typing import List, Optional, Dict
import httpx

from app.models.music import MusicSong, MusicRank

logger = logging.getLogger("music_manager")

BUILTIN_RANKS = [
    {
        "id": "3778678",
        "name": "热歌榜",
        "description": "全网最热门火爆的流行单曲",
        "cover": "https://p1.music.126.net/GHhuNnNg57zBJ7x6Wf1VzA==/109951165682121696.jpg",
        "update_frequency": "每周四更新"
    },
    {
        "id": "19723756",
        "name": "飙升榜",
        "description": "云音乐官方根据近100天单曲播放增量推荐",
        "cover": "https://p1.music.126.net/DrRIg6CrgDfVLEph9SNh7w==/18696095720518497.jpg",
        "update_frequency": "每天更新"
    },
    {
        "id": "3779629",
        "name": "新歌榜",
        "description": "最新发布的热门好听新单曲",
        "cover": "https://p1.music.126.net/N2HO1XM2tOkxAVU09UhnCw==/18979770070844786.jpg",
        "update_frequency": "每天更新"
    },
    {
        "id": "2884035",
        "name": "抖音热歌榜",
        "description": "当下短视频平台最受欢迎背景音乐",
        "cover": "https://p1.music.126.net/efrbYv18f1lP5DovrI2_8w==/109951165682126487.jpg",
        "update_frequency": "每周五更新"
    },
    {
        "id": "24381616",
        "name": "经典老歌榜",
        "description": "岁月沉淀的永恒金曲，百听不厌",
        "cover": "https://p1.music.126.net/13593683615467384/109951165682138982.jpg",
        "update_frequency": "每周更新"
    }
]

DOMESTIC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; MI 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "X-Forwarded-For": "116.25.146.177",
    "X-Real-IP": "116.25.146.177",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://music.163.com/",
}


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

    def get_ranks(self) -> List[MusicRank]:
        """获取所有可用音乐榜单"""
        return [
            MusicRank(
                id=r["id"],
                name=r["name"],
                description=r["description"],
                cover=r["cover"],
                update_frequency=r["update_frequency"],
            )
            for r in BUILTIN_RANKS
        ]

    async def get_rank_songs(self, rank_id: str, limit: int = 100) -> List[MusicSong]:
        """获取指定榜单的歌曲列表"""
        now = time.time()
        if rank_id in self._rank_cache:
            cache_time, cached_songs = self._rank_cache[rank_id]
            if now - cache_time < self._cache_ttl:
                return cached_songs[:limit]

        url = f"https://music.163.com/api/playlist/detail?id={rank_id}"
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
                        cover = t.get("album", {}).get("picUrl")
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
                                play_url=f"https://music.163.com/song/media/outer/url?id={sid}.mp3",
                            )
                        )
                    self._rank_cache[rank_id] = (now, songs)
                    return songs[:limit]
            except Exception as e:
                logger.error(f"Error fetching rank songs {rank_id}: {e}")

        return []

    async def search_songs(self, keyword: str, limit: int = 30) -> List[MusicSong]:
        """搜索歌曲（网易云主源，QQ音乐补充）"""
        results: List[MusicSong] = []
        async with httpx.AsyncClient(headers=DOMESTIC_HEADERS, timeout=6.0) as client:
            # 1. 优先搜索网易云
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
                        cover = s.get("album", {}).get("picUrl") or s.get("album", {}).get("artist", {}).get("img1v1Url")
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
                                play_url=f"https://music.163.com/song/media/outer/url?id={sid}.mp3",
                            )
                        )
            except Exception as e:
                logger.error(f"Error searching NetEase: {e}")

            # 2. 搜索 QQ 音乐（唐接口补充）
            try:
                qq_url = f"https://tang.api.s01s.cn/music_open_api.php?msg={keyword}&type=json"
                r_qq = await client.get(qq_url)
                if r_qq.status_code == 200:
                    data = r_qq.json()
                    if isinstance(data, list):
                        for item in data[:15]:
                            mid = item.get("song_mid")
                            title = item.get("song_title", "")
                            singer = item.get("singer_name", "")
                            if mid and title:
                                results.append(
                                    MusicSong(
                                        id=f"qq:{mid}",
                                        name=title,
                                        artist=singer,
                                        album="QQ音乐",
                                        platform="qq",
                                        mid=mid,
                                        cover=None,
                                        play_url=None,  # 点击播放时动态解析
                                    )
                                )
            except Exception as e:
                logger.error(f"Error searching QQ Music: {e}")

        return results

    async def get_song_play_url(self, song_id: str) -> Optional[str]:
        """获取歌曲播放直链（自动处理网易与 QQ 解析）"""
        if song_id.startswith("netease:"):
            sid = song_id.replace("netease:", "")
            return f"https://music.163.com/song/media/outer/url?id={sid}.mp3"

        if song_id.startswith("qq:"):
            mid = song_id.replace("qq:", "")
            async with httpx.AsyncClient(headers=DOMESTIC_HEADERS, timeout=6.0) as client:
                try:
                    url = f"https://api.vkeys.cn/v2/music/tencent/geturl?mid={mid}"
                    r = await client.get(url)
                    if r.status_code == 200:
                        data = r.json()
                        play_url = data.get("data", {}).get("url")
                        if play_url:
                            return play_url
                except Exception as e:
                    logger.error(f"Error resolving QQ music URL {mid}: {e}")

        return None

    async def get_song_detail(self, song_id: str) -> Optional[MusicSong]:
        """获取歌曲完整信息（包含直链、封面与歌词）"""
        if song_id.startswith("netease:"):
            sid = song_id.replace("netease:", "")
            play_url = f"https://music.163.com/song/media/outer/url?id={sid}.mp3"
            lrc = await self.get_song_lrc(song_id)

            # 获取歌曲详情与封面
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
                            cover = s.get("album", {}).get("picUrl")
                            duration = (s.get("duration", 0) or 0) // 1000
                except Exception:
                    pass

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
                try:
                    url = f"https://api.vkeys.cn/v2/music/tencent/geturl?mid={mid}"
                    r = await client.get(url)
                    if r.status_code == 200:
                        d = r.json().get("data", {})
                        lrc = await self.get_song_lrc(song_id)
                        return MusicSong(
                            id=song_id,
                            name=d.get("song", "未知"),
                            artist=d.get("singer", "未知"),
                            album=d.get("album"),
                            cover=d.get("cover"),
                            platform="qq",
                            mid=mid,
                            play_url=d.get("url"),
                            lrc=lrc,
                        )
                except Exception as e:
                    logger.error(f"Error fetching QQ song detail: {e}")

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
                try:
                    url = f"https://tang.api.s01s.cn/music_open_api.php?msg=歌词&type=json&mid={mid}"
                    r = await client.get(url)
                    if r.status_code == 200:
                        d = r.json()
                        if isinstance(d, dict):
                            return d.get("song_lyric") or d.get("lyric")
                except Exception as e:
                    logger.error(f"Error fetching QQ lyric {mid}: {e}")

        return None
