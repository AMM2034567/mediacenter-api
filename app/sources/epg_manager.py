import gzip
import logging
import os
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import xml.etree.cElementTree as ET
import httpx

logger = logging.getLogger(__name__)

# China Standard Time (UTC+8)
CST = timezone(timedelta(hours=8))


class EpgManager:
    _instance: Optional["EpgManager"] = None
    EPG_URLS = [
        "https://epg.zsdc.eu.org/t.xml.gz",
        "https://epg.zsdc.eu.org/t.xml",
    ]

    def __init__(self):
        # channel_key -> list of program dicts sorted by start_timestamp
        self._programs_by_channel: Dict[str, List[dict]] = {}
        self._last_fetch_time: float = 0.0
        self._fetch_interval: float = 4 * 3600  # Refresh every 4 hours

    @classmethod
    def get_instance(cls) -> "EpgManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def normalize_name(name: str) -> str:
        """
        标准化频道名称以匹配 EPG XML 中的 channel id:
        - 'CCTV-1 综合' / 'CCTV-1' -> 'CCTV1'
        - 'CCTV-5+ 体育赛事' -> 'CCTV5+'
        - '湖南卫视 高清' -> '湖南卫视'
        """
        clean = re.sub(r'[\s\-]+', '', name).upper()
        m = re.match(r'^(CCTV\d+\+?|CCTV4K)', clean)
        if m:
            return m.group(1)
        # 去除清晰度后缀
        clean = re.sub(r'(HD|4K|高清|超清|标清)$', '', clean, flags=re.I)
        return clean

    async def ensure_epg_loaded(self, force: bool = False):
        now = time.time()
        if not force and self._programs_by_channel and (now - self._last_fetch_time < self._fetch_interval):
            return

        for url in self.EPG_URLS:
            try:
                async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, verify=False) as client:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        content = resp.content
                        if url.endswith(".gz") or content[:2] == b"\x1f\x8b":
                            xml_bytes = gzip.decompress(content)
                        else:
                            xml_bytes = content

                        self._parse_xml(xml_bytes)
                        self._last_fetch_time = now
                        logger.info("EPG successfully loaded from %s (%d channels)", url, len(self._programs_by_channel))
                        return
            except Exception as e:
                logger.warning("Failed to fetch EPG from %s: %s", url, e)

    def _parse_xml(self, xml_bytes: bytes):
        try:
            root = ET.fromstring(xml_bytes)
        except Exception as e:
            logger.error("Failed to parse EPG XML: %s", e)
            return

        new_map: Dict[str, List[dict]] = {}

        for p in root.findall("programme"):
            raw_channel = p.get("channel") or ""
            if not raw_channel:
                continue

            channel_norm = self.normalize_name(raw_channel)
            start_str = (p.get("start") or "").strip()
            stop_str = (p.get("stop") or "").strip()
            title_elem = p.find("title")
            title = title_elem.text.strip() if title_elem is not None and title_elem.text else "节目播送中"
            desc_elem = p.find("desc")
            desc = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ""

            try:
                # 格式: 20261005220000 +0800
                start_dt = datetime.strptime(start_str[:14], "%Y%m%d%H%M%S").replace(tzinfo=CST)
                stop_dt = datetime.strptime(stop_str[:14], "%Y%m%d%H%M%S").replace(tzinfo=CST)
            except Exception:
                continue

            prog_item = {
                "title": title,
                "desc": desc,
                "start": start_dt.strftime("%H:%M"),
                "stop": stop_dt.strftime("%H:%M"),
                "date": start_dt.strftime("%Y-%m-%d"),
                "start_timestamp": int(start_dt.timestamp()),
                "stop_timestamp": int(stop_dt.timestamp()),
            }

            if channel_norm not in new_map:
                new_map[channel_norm] = []
            new_map[channel_norm].append(prog_item)

        # 按开始时间排序
        for ch in new_map:
            new_map[ch].sort(key=lambda x: x["start_timestamp"])

        self._programs_by_channel = new_map

    def _find_programs(self, channel_name: str) -> Optional[List[dict]]:
        ch_key = self.normalize_name(channel_name)
        programs = self._programs_by_channel.get(ch_key)
        if programs:
            return programs

        # 模糊查找
        for k, v in self._programs_by_channel.items():
            if ch_key in k or k in ch_key:
                return v
        return None

    def get_current_program(self, channel_name: str) -> Optional[dict]:
        programs = self._find_programs(channel_name)
        if not programs:
            return None

        now_ts = int(datetime.now(CST).timestamp())
        current_prog = None
        next_prog = None

        for idx, p in enumerate(programs):
            if p["start_timestamp"] <= now_ts <= p["stop_timestamp"]:
                current_prog = p
                if idx + 1 < len(programs):
                    next_prog = programs[idx + 1]
                break
            elif p["start_timestamp"] > now_ts:
                if next_prog is None:
                    next_prog = p
                break

        if not current_prog and not next_prog:
            return None

        progress = 0.0
        if current_prog:
            total_sec = current_prog["stop_timestamp"] - current_prog["start_timestamp"]
            elapsed_sec = now_ts - current_prog["start_timestamp"]
            if total_sec > 0:
                progress = round(min(1.0, max(0.0, elapsed_sec / total_sec)), 2)

        return {
            "channel": channel_name,
            "current": current_prog,
            "next": next_prog,
            "progress": progress,
        }

    def get_batch_current(self, channel_names: List[str]) -> Dict[str, Optional[dict]]:
        result = {}
        for name in channel_names:
            result[name] = self.get_current_program(name)
        return result

    def get_schedule(self, channel_name: str, date_str: Optional[str] = None) -> List[dict]:
        programs = self._find_programs(channel_name)
        if not programs:
            return []

        if not date_str:
            date_str = datetime.now(CST).strftime("%Y-%m-%d")

        return [p for p in programs if p["date"] == date_str]
