from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.models.media import MediaType

class LiveStreamLine(BaseModel):
    name: str = Field(default="线路1", description="线路名称/描述，如 线路1 (fanmingming) / 线路2 (YueChan)")
    url: str = Field(..., description="直播流播放地址，如 http://.../index.m3u8")
    status: Optional[str] = Field(default="unknown", description="探测状态: ok, slow, down, unknown")
    latency_ms: Optional[float] = Field(default=None, description="探测延迟毫秒数")

class LiveChannel(BaseModel):
    id: str = Field(..., description="频道唯一ID，如 live:cctv1, radio:cnr1")
    name: str = Field(..., description="频道标准名称，如 CCTV-1 综合, 湖南卫视, CNR 中国之声")
    raw_name: Optional[str] = Field(None, description="原始频道名")
    group: str = Field(default="其他", description="所属分组，如 央视频道, 卫视频道, 地方频道, 广播电台")
    logo: Optional[str] = Field(None, description="台标Logo链接")
    tvg_id: Optional[str] = Field(None, description="EPG电视指南匹配ID")
    media_type: MediaType = Field(default=MediaType.LIVE, description="媒体类型: live (电视直播) 或 music/live (广播电台)")
    is_radio: bool = Field(default=False, description="是否为纯音频/广播电台")
    lines: List[LiveStreamLine] = Field(default_factory=list, description="聚合的多线路播放列表")
    current_url: Optional[str] = Field(None, description="当前默认推荐可用的流地址")

class LiveGroup(BaseModel):
    name: str = Field(..., description="分组名称")
    count: int = Field(default=0, description="频道数量")
    icon: Optional[str] = Field(None, description="分组图标标识")
    is_radio: bool = Field(default=False, description="是否为广播电台分组")

class RadioStation(BaseModel):
    station_uuid: str = Field(..., description="Radio-Browser唯一UUID")
    name: str = Field(..., description="电台名称")
    url: str = Field(..., description="播放音频流URL")
    favicon: Optional[str] = Field(None, description="电台图标")
    country: Optional[str] = Field(None, description="国家")
    countrycode: Optional[str] = Field(None, description="国家代码")
    state: Optional[str] = Field(None, description="省份/地区")
    tags: Optional[str] = Field(None, description="风格分类标签")
    codec: Optional[str] = Field(None, description="音频编码格式: MP3, AAC, etc.")
    bitrate: Optional[int] = Field(None, description="码率 kbps")
    votes: Optional[int] = Field(0, description="点赞数")
    clickcount: Optional[int] = Field(0, description="热度点击数")

class LiveProbeResult(BaseModel):
    url: str
    is_alive: bool
    status_code: int
    latency_ms: float
    content_type: Optional[str] = None
