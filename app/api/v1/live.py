import asyncio
from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException, Response

from app.models.media import ApiResponse
from app.models.live import LiveChannel, LiveGroup, RadioStation, LiveProbeResult
from app.sources.live_manager import LiveManager
from app.sources.radio_manager import RadioManager
from app.sources.epg_manager import EpgManager

router = APIRouter(prefix="/live", tags=["Live & Radio"])

@router.get("/groups", response_model=ApiResponse[List[LiveGroup]], summary="获取所有直播与电台分类分组")
async def get_live_groups():
    mgr = LiveManager.get_instance()
    groups = mgr.list_groups()
    return ApiResponse(data=groups)

@router.get("/channels", response_model=ApiResponse[List[LiveChannel]], summary="获取直播频道列表(支持分组与搜索)")
async def get_live_channels(
    group: Optional[str] = Query(None, description="指定分组名称，如: 央视频道, 卫视频道, 广播电台"),
    kw: Optional[str] = Query(None, description="搜索关键词，如: CCTV, 湖南, 交通"),
    is_radio: Optional[bool] = Query(None, description="是否过滤纯音频广播电台")
):
    mgr = LiveManager.get_instance()
    channels = mgr.list_channels(group=group, keyword=kw)
    if is_radio is not None:
        channels = [c for c in channels if c.is_radio == is_radio]
    return ApiResponse(data=channels)

@router.get("/channel/{channel_id}", response_model=ApiResponse[LiveChannel], summary="获取单个频道详情与多线路播放地址")
async def get_channel_detail(channel_id: str):
    mgr = LiveManager.get_instance()
    channel = mgr.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="未找到该频道")
    return ApiResponse(data=channel)

@router.get("/channel/{channel_id}/probe-lines", response_model=ApiResponse[LiveChannel], summary="对频道路线进行在线测速与健康度重排")
async def probe_channel_lines(channel_id: str):
    mgr = LiveManager.get_instance()
    channel = await mgr.probe_and_sort_channel_lines(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="未找到该频道")
    return ApiResponse(data=channel)

@router.get("/radio/top", response_model=ApiResponse[List[RadioStation]], summary="获取热门广播电台 (Radio-Browser + 内置央广)")
async def get_top_radio_stations(
    limit: int = Query(50, ge=1, le=100, description="返回数量"),
    country: str = Query("CN", description="国家代码，默认中国 CN")
):
    radio_mgr = RadioManager.get_instance()
    stations = await radio_mgr.get_top_stations(limit=limit, country_code=country)
    return ApiResponse(data=stations)

@router.get("/radio/search", response_model=ApiResponse[List[RadioStation]], summary="关键词搜索广播电台")
async def search_radio_stations(
    kw: str = Query(..., description="电台名称或关键词"),
    limit: int = Query(40, ge=1, le=80, description="返回数量")
):
    radio_mgr = RadioManager.get_instance()
    stations = await radio_mgr.search_stations(keyword=kw, limit=limit)
    return ApiResponse(data=stations)

@router.post("/refresh", response_model=ApiResponse[dict], summary="重新从远程 GitHub/CF 镜像同步刷新直播与电台源")
async def refresh_live_sources():
    mgr = LiveManager.get_instance()
    asyncio.create_task(mgr.reload_all_sources())
    return ApiResponse(data={
        "status": "refreshing",
        "message": "正在后台同步刷新 IPTV 与 Radio 订阅源，聚合完成后将自动生效"
    })

@router.get("/probe", response_model=ApiResponse[LiveProbeResult], summary="极速探测直播/音频串流连通性与网络延迟")
async def probe_live_stream(url: str = Query(..., description="待测直播流 URL")):
    mgr = LiveManager.get_instance()
    res = await mgr.probe_stream(url)
    return ApiResponse(data=res)

@router.get("/epg/current", response_model=ApiResponse[Optional[dict]], summary="获取指定频道当前与下一节目信息")
async def get_current_epg(channel: str = Query(..., description="频道名称，如: CCTV-1, 湖南卫视")):
    epg_mgr = EpgManager.get_instance()
    await epg_mgr.ensure_epg_loaded()
    data = epg_mgr.get_current_program(channel)
    return ApiResponse(data=data)

@router.get("/epg/current-batch", response_model=ApiResponse[dict], summary="批量获取多个频道当前正在播出的节目")
async def get_batch_current_epg(channels: str = Query(..., description="以逗号分隔的频道名称列表")):
    epg_mgr = EpgManager.get_instance()
    await epg_mgr.ensure_epg_loaded()
    ch_list = [c.strip() for c in channels.split(",") if c.strip()]
    data = epg_mgr.get_batch_current(ch_list)
    return ApiResponse(data=data)

@router.get("/epg/schedule", response_model=ApiResponse[List[dict]], summary="获取指定频道单日完整节目单")
async def get_channel_schedule(
    channel: str = Query(..., description="频道名称，如: CCTV-1, 湖南卫视"),
    date: Optional[str] = Query(None, description="日期，格式: YYYY-MM-DD，默认今天")
):
    epg_mgr = EpgManager.get_instance()
    await epg_mgr.ensure_epg_loaded()
    schedule = epg_mgr.get_schedule(channel, date_str=date)
    return ApiResponse(data=schedule)

@router.get("/export.m3u", summary="导出聚合后的标准 M3U 播放列表")
async def export_m3u_playlist():
    mgr = LiveManager.get_instance()
    channels = mgr.list_channels()

    m3u_lines = ["#EXTM3U x-tvg-url=\"https://epg.zsdc.eu.org/t.xml.gz\""]
    for ch in channels:
        for idx, line in enumerate(ch.lines, start=1):
            logo_attr = f' tvg-logo="{ch.logo}"' if ch.logo else ""
            id_attr = f' tvg-id="{ch.tvg_id or ch.name}"'
            group_attr = f' group-title="{ch.group}"'
            line_suffix = f" (线路{idx})" if len(ch.lines) > 1 else ""
            m3u_lines.append(f'#EXTINF:-1{id_attr}{logo_attr}{group_attr},{ch.name}{line_suffix}')
            m3u_lines.append(line.url)

    content = "\n".join(m3u_lines)
    return Response(
        content=content,
        media_type="application/vnd.apple.mpegurl",
        headers={"Content-Disposition": "attachment; filename=mediacenter_live.m3u"}
    )

