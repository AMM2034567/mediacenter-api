import asyncio
import logging
import re
import time
from typing import Dict, List, Optional, Tuple
import httpx

from app.models.live import LiveChannel, LiveGroup, LiveStreamLine, LiveProbeResult
from app.models.media import MediaType
from app.sources.radio_manager import RadioManager
from app.config import settings

try:
    from app.sources.preloaded_live_data import PRELOADED_CHANNELS
except ImportError:
    PRELOADED_CHANNELS = []

logger = logging.getLogger(__name__)

# CCTV 规范名称映射字典
CCTV_CANONICAL_NAMES: Dict[str, str] = {
    "1": "CCTV-1 综合",
    "2": "CCTV-2 财经",
    "3": "CCTV-3 综艺",
    "4": "CCTV-4 中文国际",
    "5": "CCTV-5 体育",
    "5+": "CCTV-5+ 体育赛事",
    "6": "CCTV-6 电影",
    "7": "CCTV-7 国防军事",
    "8": "CCTV-8 电视剧",
    "9": "CCTV-9 纪录",
    "10": "CCTV-10 科教",
    "11": "CCTV-11 戏曲",
    "12": "CCTV-12 社会与法",
    "13": "CCTV-13 新闻",
    "14": "CCTV-14 少儿",
    "15": "CCTV-15 音乐",
    "16": "CCTV-16 奥林匹克",
    "17": "CCTV-17 农业农村",
    "4K": "CCTV-4K 超高清",
    "8K": "CCTV-8K 超高清",
}

# 主要卫视频道列表
MAJOR_SATELLITE_CHANNELS = [
    "湖南卫视", "浙江卫视", "江苏卫视", "东方卫视", "北京卫视",
    "广东卫视", "深圳卫视", "山东卫视", "四川卫视", "河南卫视",
    "湖北卫视", "安徽卫视", "江西卫视", "辽宁卫视", "黑龙江卫视",
    "吉林卫视", "天津卫视", "重庆卫视", "贵州卫视", "广西卫视",
    "云南卫视", "陕西卫视", "甘肃卫视", "青海卫视", "宁夏卫视",
    "新疆卫视", "西藏卫视", "内蒙古卫视", "东南卫视", "河北卫视",
    "山西卫视", "海南卫视", "兵团卫视"
]

# 高可用内置基础频道（真实国内电信/联通/移动公网实测 20ms~80ms 秒开流）
BUILTIN_LIVE_CHANNELS: List[LiveChannel] = [
    LiveChannel(
        id="live:cctv1综合",
        name="CCTV-1 综合",
        raw_name="CCTV-1 综合",
        group="央视频道",
        logo="https://live.fanmingming.com/tv/cctv1.png",
        tvg_id="CCTV1",
        lines=[
            LiveStreamLine(name="线路1 (公网CDN/秒开)", url="http://74.91.26.218:82/live/cctv1hd.m3u8"),
            LiveStreamLine(name="线路2 (Guovin备用)", url="http://63.141.230.178:82/gslb/zbdq5.m3u8?id=cctv1hd"),
            LiveStreamLine(name="线路3 (1080P超清)", url="http://204.12.221.218:8181/3m1080p/cctv1.m3u8"),
        ],
        current_url="http://74.91.26.218:82/live/cctv1hd.m3u8"
    ),
    LiveChannel(
        id="live:cctv13新闻",
        name="CCTV-13 新闻",
        raw_name="CCTV-13 新闻",
        group="央视频道",
        logo="https://live.fanmingming.com/tv/cctv13.png",
        tvg_id="CCTV13",
        lines=[
            LiveStreamLine(name="线路1 (阿里CDN专线/秒开)", url="http://ali-m-l.cztv.com/channels/lantian/channel21/1080p.m3u8"),
            LiveStreamLine(name="线路2 (公网CDN备用)", url="http://74.91.26.218:82/live/cctv13hd.m3u8"),
            LiveStreamLine(name="线路3 (Guovin备用)", url="http://63.141.230.178:82/gslb/zbdq5.m3u8?id=cctv13hd"),
        ],
        current_url="http://ali-m-l.cztv.com/channels/lantian/channel21/1080p.m3u8"
    ),
    LiveChannel(
        id="live:湖南卫视",
        name="湖南卫视",
        raw_name="湖南卫视",
        group="卫视频道",
        logo="https://live.fanmingming.com/tv/hunan.png",
        tvg_id="湖南卫视",
        lines=[
            LiveStreamLine(name="线路1 (快手CDN专线/秒开)", url="https://txmov2.a.kwimgs.com/bs3/video-hls/5199687338554291078_hlsb.m3u8"),
            LiveStreamLine(name="线路2 (Guovin备用)", url="http://63.141.230.178:82/gslb/zbdq5.m3u8?id=hunanhd"),
            LiveStreamLine(name="线路3 (公网备用)", url="http://198.204.228.26/live/hunanhd.m3u8"),
        ],
        current_url="https://txmov2.a.kwimgs.com/bs3/video-hls/5199687338554291078_hlsb.m3u8"
    ),
    LiveChannel(
        id="live:浙江卫视",
        name="浙江卫视",
        raw_name="浙江卫视",
        group="卫视频道",
        logo="https://live.fanmingming.com/tv/zhejiang.png",
        tvg_id="浙江卫视",
        lines=[
            LiveStreamLine(name="线路1 (阿里CDN专线/秒开)", url="http://ali-m-l.cztv.com/channels/lantian/channel01/1080p.m3u8"),
            LiveStreamLine(name="线路2 (Guovin备用)", url="http://63.141.230.178:82/gslb/zbdq5.m3u8?id=zhejianghd"),
            LiveStreamLine(name="线路3 (公网备用)", url="http://198.204.228.26/live/zhejianghd.m3u8"),
        ],
        current_url="http://ali-m-l.cztv.com/channels/lantian/channel01/1080p.m3u8"
    ),
]


class LiveManager:
    _instance: Optional["LiveManager"] = None

    def __init__(self):
        self._channels: Dict[str, LiveChannel] = {}
        self._groups: Dict[str, int] = {}
        self._last_updated: float = 0
        self._is_loading: bool = False

        # 1. 优先加载预载聚合频道（支持 Serverless 毫秒级冷启动）
        if PRELOADED_CHANNELS:
            for item in PRELOADED_CHANNELS:
                ch = LiveChannel.model_validate(item)
                self._channels[ch.id] = ch
            logger.info(f"Loaded {len(self._channels)} preloaded live channels.")
        else:
            for ch in BUILTIN_LIVE_CHANNELS:
                self._channels[ch.id] = ch
        self._rebuild_groups()

    @classmethod
    def get_instance(cls) -> "LiveManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def get_channel_id(canonical_name: str) -> str:
        key = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', canonical_name).lower()
        return f"live:{key}"

    @staticmethod
    def normalize_group_name(group_name: str, fallback_group: str = "地方频道") -> str:
        g = group_name.strip()
        if any(k in g for k in ["央视", "CCTV", "CGTN"]):
            return "央视频道"
        if "卫视" in g:
            return "卫视频道"
        if any(k in g for k in ["广播", "电台", "FM", "音频", "之声"]):
            return "广播电台"
        if any(k in g for k in ["电影", "影院", "剧场", "轮播", "影视", "4K", "8K"]):
            return "轮播影院"
        if any(k in g for k in ["港", "台", "澳门", "国际"]):
            return "港澳台"
        if any(k in g for k in ["地方", "都市", "新闻", "民生"]):
            return "地方频道"
        return fallback_group


    @staticmethod
    def normalize_channel_name(raw_name: str) -> Tuple[str, str]:
        """
        智能频道名称归一化与分类推断:
        返回 (标准频道名称, 推荐分组名)
        例如: 'CCTV-1 高清' -> ('CCTV-1 综合', '央视频道')
              '湖南卫视 1080P' -> ('湖南卫视', '卫视频道')
        """
        cleaned = raw_name.strip()
        # 清理常见的清晰度干扰后缀
        cleaned = re.sub(r'(?:\[.*?\]|\(.*?\)|HD|FHD|UHD|4K|8K|1080[pP]|720[pP]|高清|超清|标清|\+|HEVC|IPv[46])', '', cleaned, flags=re.IGNORECASE).strip()

        # 1. 匹配 CCTV 序列
        cctv_match = re.search(r'CCTV[\s\-_]*(\d+\+?|4K|8K)', raw_name, flags=re.IGNORECASE)
        if cctv_match:
            num = cctv_match.group(1).upper()
            canonical = CCTV_CANONICAL_NAMES.get(num, f"CCTV-{num}")
            return canonical, "央视频道"

        if "CGTN" in raw_name.upper():
            return raw_name.strip(), "央视频道"

        # 2. 匹配 卫视频道
        for w in MAJOR_SATELLITE_CHANNELS:
            core_name = w.replace("卫视", "")
            if core_name in raw_name and ("卫视" in raw_name or "台" in raw_name or len(raw_name) <= 6):
                return w, "卫视频道"

        if "卫视" in raw_name:
            # 提取如 '厦门卫视'
            match = re.search(r'([\u4e00-\u9fa5]{2,4}卫视)', raw_name)
            if match:
                return match.group(1), "卫视频道"

        # 3. 匹配 轮播/影院/剧场
        if any(k in raw_name for k in ["电影", "影院", "剧场", "经典", "动画", "纪录"]):
            return cleaned or raw_name.strip(), "轮播影院"

        # 4. 匹配 广播/电台
        if any(k in raw_name for k in ["广播", "电台", "FM", "之声", "CNR", "CRI"]):
            return cleaned or raw_name.strip(), "广播电台"

        # 默认归类
        return cleaned or raw_name.strip(), "地方频道"

    def _rebuild_groups(self):
        """重新统计分组与频道数量"""
        group_counts: Dict[str, int] = {}
        for ch in self._channels.values():
            g = ch.group
            group_counts[g] = group_counts.get(g, 0) + 1
        self._groups = group_counts

    def list_groups(self) -> List[LiveGroup]:
        """获取所有可用分组列表（保证央视、卫视、广播等排在最前）"""
        priority_order = ["央视频道", "卫视频道", "地方频道", "轮播影院", "广播电台", "其他"]
        result: List[LiveGroup] = []

        # 按照优先级排序
        for g_name in priority_order:
            if g_name in self._groups:
                result.append(LiveGroup(
                    name=g_name,
                    count=self._groups[g_name],
                    is_radio=(g_name == "广播电台")
                ))

        # 其他未在优先级列表中的分组
        for g_name, count in sorted(self._groups.items()):
            if g_name not in priority_order:
                result.append(LiveGroup(
                    name=g_name,
                    count=count,
                    is_radio=("广播" in g_name or "电台" in g_name or "FM" in g_name)
                ))

        return result

    def list_channels(self, group: Optional[str] = None, keyword: Optional[str] = None) -> List[LiveChannel]:
        """按分组和关键词检索频道"""
        channels = list(self._channels.values())

        if group:
            channels = [c for c in channels if c.group == group]

        if keyword:
            kw = keyword.lower().strip()
            channels = [
                c for c in channels
                if kw in c.name.lower() or (c.raw_name and kw in c.raw_name.lower()) or kw in c.group.lower()
            ]

        return channels

    def get_channel(self, channel_id: str) -> Optional[LiveChannel]:
        return self._channels.get(channel_id)

    def _parse_m3u(self, content: str, source_tag: str, target_dict: Optional[Dict[str, LiveChannel]] = None):
        """解析标准 M3U 直播源内容并聚合并入 _channels 或 target_dict"""
        channels_map = target_dict if target_dict is not None else self._channels
        lines = content.splitlines()
        current_meta = {}

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("#EXTINF:"):
                # 解析属性: tvg-name, tvg-logo, group-title, 频道标题
                current_meta = {}
                logo_match = re.search(r'tvg-logo="([^"]+)"', line)
                if logo_match:
                    current_meta["logo"] = logo_match.group(1)

                name_match = re.search(r'tvg-name="([^"]+)"', line)
                if name_match:
                    current_meta["tvg_name"] = name_match.group(1)

                id_match = re.search(r'tvg-id="([^"]+)"', line)
                if id_match:
                    current_meta["tvg_id"] = id_match.group(1)

                group_match = re.search(r'group-title="([^"]+)"', line)
                if group_match:
                    current_meta["group"] = group_match.group(1)

                # 逗号后为展示标题
                parts = line.split(",", 1)
                raw_name = parts[1].strip() if len(parts) > 1 else current_meta.get("tvg_name", "未命名频道")
                current_meta["raw_name"] = raw_name

            elif not line.startswith("#") and (line.startswith("http://") or line.startswith("https://") or line.startswith("rtmp://")):
                stream_url = line
                # 剔除已失效的移动内网与被 Cloudflare 1034 阻断的不可用源
                if any(bad in stream_url for bad in ["cmvideo.cn", "bestlive.itv", "1.1.1.2", "wasusy", "bestzb"]):
                    continue

                raw_name = current_meta.get("raw_name", "未命名频道")
                canonical_name, inferred_group = self.normalize_channel_name(raw_name)

                # 分组规范化映射
                m3u_group = current_meta.get("group", "")
                group = self.normalize_group_name(m3u_group, fallback_group=inferred_group)

                # 构造全局一致 Channel ID
                channel_id = self.get_channel_id(canonical_name)

                logo = current_meta.get("logo")
                tvg_id = current_meta.get("tvg_id")

                if channel_id in channels_map:
                    # 频道已存在 -> 合并追加线路 (线路1, 线路2...)
                    existing = channels_map[channel_id]
                    if not any(l.url == stream_url for l in existing.lines):
                        line_index = len(existing.lines) + 1
                        existing.lines.append(LiveStreamLine(
                            name=f"线路{line_index} ({source_tag})",
                            url=stream_url
                        ))
                    if logo and not existing.logo:
                        existing.logo = logo
                    if tvg_id and not existing.tvg_id:
                        existing.tvg_id = tvg_id
                else:
                    # 新增频道
                    channels_map[channel_id] = LiveChannel(
                        id=channel_id,
                        name=canonical_name,
                        raw_name=raw_name,
                        group=group,
                        logo=logo,
                        tvg_id=tvg_id,
                        media_type=MediaType.LIVE,
                        is_radio=("广播" in group or "电台" in group),
                        lines=[LiveStreamLine(name=f"线路1 ({source_tag})", url=stream_url)],
                        current_url=stream_url
                    )

                current_meta = {}

    def _parse_txt(self, content: str, source_tag: str, target_dict: Optional[Dict[str, LiveChannel]] = None):
        """解析 TXT (DIYP/TVBox) 格式直播源 (如 央视频道,#genre#)"""
        channels_map = target_dict if target_dict is not None else self._channels
        lines = content.splitlines()
        current_group = "地方频道"

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if "#genre#" in line:
                raw_genre = line.split(",")[0].strip()
                current_group = self.normalize_group_name(raw_genre, fallback_group="地方频道")
                continue

            parts = line.split(",", 1)
            if len(parts) != 2:
                continue

            raw_name, url_part = parts[0].strip(), parts[1].strip()
            canonical_name, inferred_group = self.normalize_channel_name(raw_name)
            group = self.normalize_group_name(current_group, fallback_group=inferred_group)

            channel_id = self.get_channel_id(canonical_name)

            urls = [u.strip() for u in url_part.split("#") if u.strip()]
            for u in urls:
                if any(bad in u for bad in ["cmvideo.cn", "bestlive.itv", "1.1.1.2", "wasusy", "bestzb"]):
                    continue
                if channel_id in channels_map:
                    existing = channels_map[channel_id]
                    if not any(l.url == u for l in existing.lines):
                        line_index = len(existing.lines) + 1
                        existing.lines.append(LiveStreamLine(
                            name=f"线路{line_index} ({source_tag})",
                            url=u
                        ))
                else:
                    channels_map[channel_id] = LiveChannel(
                        id=channel_id,
                        name=canonical_name,
                        raw_name=raw_name,
                        group=group,
                        media_type=MediaType.LIVE,
                        is_radio=("广播" in group or "电台" in group),
                        lines=[LiveStreamLine(name=f"线路1 ({source_tag})", url=u)],
                        current_url=u
                    )

    async def _fetch_url_with_cdn_fallback(self, url: str) -> Optional[str]:
        """
        通过直连与 Cloudflare / GitHub 代理镜像回退机制拉取订阅源内容，突破网络阻断
        """
        candidate_urls: List[str] = []
        
        # 1. 直连
        candidate_urls.append(url)

        # 2. 如果是 GitHub Raw 链接，自动生成 Cloudflare CDN 镜像与 GitMirror 备选
        if "raw.githubusercontent.com" in url:
            for prefix in settings.GITHUB_CDN_PREFIXES:
                if prefix:
                    candidate_urls.append(f"{prefix}{url}")

        for target in candidate_urls:
            try:
                async with httpx.AsyncClient(timeout=9.0, follow_redirects=True) as client:
                    resp = await client.get(target)
                    if resp.status_code == 200 and len(resp.text) > 100:
                        logger.info(f"Successfully fetched IPTV source from: {target} (len={len(resp.text)})")
                        return resp.text
            except Exception as e:
                logger.debug(f"Failed to fetch {target}: {e}")

        logger.warning(f"All candidate URLs failed for {url}")
        return None

    async def reload_all_sources(self) -> int:
        """并发拉取配置的 IPTV 与 Radio 订阅源，自动去重聚合"""
        if self._is_loading:
            return len(self._channels)

        self._is_loading = True
        logger.info("Starting reload of all IPTV and Radio sources...")

        # 构建新频道集合：复制现有内存中频道，保证拉取期间查询不受任何影响
        new_channels: Dict[str, LiveChannel] = {}
        for ch_id, ch in self._channels.items():
            new_channels[ch_id] = ch.model_copy(deep=True)

        # 1. 并发抓取 IPTV 订阅源
        async def fetch_one_source(idx: int, src_url: str):
            source_tag = f"源{idx}"
            if "fanmingming" in src_url:
                source_tag = "范明明"
            elif "YueChan" in src_url:
                source_tag = "YueChan"
            elif "Guovin" in src_url:
                source_tag = "Guovin"
            content = await self._fetch_url_with_cdn_fallback(src_url)
            return source_tag, content

        results = await asyncio.gather(*[
            fetch_one_source(idx, url)
            for idx, url in enumerate(settings.IPTV_SOURCE_URLS, start=1)
        ], return_exceptions=True)

        for res in results:
            if isinstance(res, tuple):
                source_tag, content = res
                if content:
                    if "#EXTM3U" in content or "#EXTINF:" in content:
                        self._parse_m3u(content, source_tag, target_dict=new_channels)
                    else:
                        self._parse_txt(content, source_tag, target_dict=new_channels)

        # 2. 抓取 Radio-Browser 广播电台与内置高品质广播
        try:
            radio_mgr = RadioManager.get_instance()
            top_radios = await radio_mgr.get_top_stations(limit=60)
            radio_channels = radio_mgr.to_live_channels(top_radios)
            for rc in radio_channels:
                new_channels[rc.id] = rc
            logger.info(f"Integrated {len(radio_channels)} radio stations into LiveManager.")
        except Exception as e:
            logger.warning(f"Error integrating Radio-Browser: {e}")

        # 对所有频道的线路进行智能质量评分与排序 (优质专线 CDN / HTTPS / IPv4 优先)
        for ch in new_channels.values():
            self._sort_channel_lines(ch)

        # 原子更新
        self._channels = new_channels
        self._rebuild_groups()
        self._last_updated = time.time()
        self._is_loading = False

        total_lines = sum(len(c.lines) for c in self._channels.values())
        logger.info(f"LiveManager loaded {len(self._channels)} channels with {total_lines} redundant stream lines across {len(self._groups)} groups!")
        return len(self._channels)

    @staticmethod
    def _score_line(line: LiveStreamLine) -> int:
        """
        根据流媒体地址特征计算优先级评分：
        1. 专线 CDN (cztv, kwimgs, migu, cctv.cn, txmov2, 74.91) -> 100 分
        2. 标准公网 HTTPS -> 80 分
        3. 标准公网 HTTP -> 60 分
        4. IPv6 地址 [2409:...] -> 15 分 (许多车机与公网 Wi-Fi 不支持 IPv6 握手)
        5. 内网保留私有 IP -> 0 分
        """
        url = line.url.lower().strip()
        if "[" in url and "]" in url:
            return 15
        if any(bad in url for bad in ["192.168.", "10.", "172.16.", "127.0.0.1"]):
            return 0
        if any(fast in url for fast in [
            "cztv.com", "kwimgs.com", "txmov2", "miguvideo.com",
            "cctv.cn", "ourdvpss", "74.91.26.218", "63.141.230.178"
        ]):
            return 100
        if url.startswith("https://"):
            return 80
        if url.startswith("http://"):
            return 60
        return 30

    def _sort_channel_lines(self, channel: LiveChannel):
        """对单个频道的线路按综合得分排序，并按顺序重命名"""
        if not channel.lines or len(channel.lines) <= 1:
            return
        channel.lines.sort(key=self._score_line, reverse=True)
        for idx, l in enumerate(channel.lines, start=1):
            match = re.search(r'\((.*?)\)', l.name)
            tag = f" ({match.group(1)})" if match else ""
            l.name = f"线路{idx}{tag}"
        if channel.lines:
            channel.current_url = channel.lines[0].url

    async def probe_stream(self, url: str) -> LiveProbeResult:
        """毫秒级快速探测直播流的连通性与网络延迟"""
        start = time.perf_counter()
        headers = {"User-Agent": "MediaCenterLive/1.0"}
        
        try:
            async with httpx.AsyncClient(headers=headers, timeout=3.5, follow_redirects=True) as client:
                # 优先尝试 HEAD，若405/403则降级为只读前1字节的 Range GET
                try:
                    resp = await client.head(url)
                except Exception:
                    resp = await client.get(url, headers={"Range": "bytes=0-1"})

                latency = (time.perf_counter() - start) * 1000.0
                is_alive = resp.status_code in (200, 206, 301, 302)
                return LiveProbeResult(
                    url=url,
                    is_alive=is_alive,
                    status_code=resp.status_code,
                    latency_ms=round(latency, 1),
                    content_type=resp.headers.get("content-type")
                )
        except Exception:
            latency = (time.perf_counter() - start) * 1000.0
            return LiveProbeResult(
                url=url,
                is_alive=False,
                status_code=504,
                latency_ms=round(latency, 1)
            )

    async def probe_and_sort_channel_lines(self, channel_id: str) -> Optional[LiveChannel]:
        """对指定频道的所有备选线路进行并发探测，按健康度与低延迟重排"""
        ch = self._channels.get(channel_id)
        if not ch or not ch.lines:
            return ch

        headers = {"User-Agent": "MediaCenterLive/1.0"}
        async with httpx.AsyncClient(headers=headers, timeout=2.5, follow_redirects=True) as client:
            async def probe_single_line(line: LiveStreamLine):
                start = time.perf_counter()
                try:
                    if "[" in line.url and "]" in line.url:
                        line.status = "slow"
                        line.latency_ms = 999.0
                        return

                    try:
                        resp = await client.head(line.url)
                    except Exception:
                        resp = await client.get(line.url, headers={"Range": "bytes=0-1"})

                    latency = (time.perf_counter() - start) * 1000.0
                    if resp.status_code in (200, 206, 301, 302):
                        line.status = "ok"
                        line.latency_ms = round(latency, 1)
                    else:
                        line.status = "down"
                        line.latency_ms = round(latency, 1)
                except Exception:
                    line.status = "down"
                    line.latency_ms = round((time.perf_counter() - start) * 1000.0, 1)

            await asyncio.gather(*[probe_single_line(l) for l in ch.lines], return_exceptions=True)

        def sort_key(l: LiveStreamLine):
            status_weight = 0 if l.status == "ok" else (1 if l.status == "slow" else 2)
            lat = l.latency_ms if l.latency_ms is not None else 9999.0
            return (status_weight, lat)

        ch.lines.sort(key=sort_key)
        for idx, l in enumerate(ch.lines, start=1):
            match = re.search(r'\((.*?)\)', l.name)
            tag = f" ({match.group(1)})" if match else ""
            l.name = f"线路{idx}{tag}"

        if ch.lines:
            ch.current_url = ch.lines[0].url

        return ch
