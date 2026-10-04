import logging
import time
from typing import Dict, Tuple
from fastapi import APIRouter, Query, HTTPException

from app.models.media import ApiResponse, ParsedStream, ProbeResult
from app.core.stream_sniffer import parse_and_sniff_stream, probe_stream

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/parse", tags=["Stream Parse"])

# In-memory cache for parsed streams: { raw_url: (timestamp, ParsedStream) }
_parse_cache: Dict[str, Tuple[float, ParsedStream]] = {}
CACHE_TTL = 3600  # 1 hour


@router.get("", response_model=ApiResponse[ParsedStream])
async def parse_stream(
    url: str = Query(..., min_length=5, description="待解析播放的视频或解析页链接")
):
    """
    智能流媒体解析与嗅探接口：
    1. 自动识别直链并获取最终重定向流
    2. 穿透多层网页播放器、Iframe与JS配置提取底层纯净 .m3u8 / .mp4
    3. 自适应生成防盗链请求头 (Referer / User-Agent)
    """
    cleaned_url = url.strip()
    now = time.time()

    # Check cache
    if cleaned_url in _parse_cache:
        cached_time, cached_res = _parse_cache[cleaned_url]
        if now - cached_time < CACHE_TTL:
            return ApiResponse(code=0, message="ok (cached)", data=cached_res)

    try:
        result = await parse_and_sniff_stream(cleaned_url)
        _parse_cache[cleaned_url] = (now, result)
        return ApiResponse(code=0, message="ok", data=result)
    except Exception as e:
        logger.error(f"Error parsing stream {cleaned_url}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse stream: {e}")


@router.get("/probe", response_model=ApiResponse[ProbeResult])
async def probe_stream_latency(
    url: str = Query(..., min_length=5, description="待测速的流媒体链接")
):
    """
    流媒体快速测速与健康检测预检接口：
    检测视频流连接状态、测速延迟(ms)、HTTP状态与响应类型
    """
    cleaned_url = url.strip()
    try:
        res = await probe_stream(cleaned_url)
        return ApiResponse(code=0, message="ok", data=res)
    except Exception as e:
        logger.error(f"Error probing stream {cleaned_url}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to probe stream: {e}")
