from enum import Enum
from typing import List, Optional, Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")

class MediaType(str, Enum):
    VIDEO = "video"
    ANIME = "anime"
    LIVE = "live"
    MUSIC = "music"
    COMIC = "comic"

class Episode(BaseModel):
    name: str = Field(..., description="剧集名称，如：第01集 / HD中字")
    url: str = Field(..., description="直接播放串流链接，如 .m3u8 或 .mp4")

class PlayRoute(BaseModel):
    name: str = Field(..., description="播放线路名称，如：蓝光线路 / 默认线路")
    episodes: List[Episode] = Field(default_factory=list, description="选集列表")

class SearchItem(BaseModel):
    id: str = Field(..., description="全局唯一媒体标识，如 maccms:iqiyizyapi:12345")
    title: str = Field(..., description="标题名称")
    cover: Optional[str] = Field(None, description="海报图片链接")
    source_key: str = Field(..., description="数据源标识，如 iqiyizyapi.com")
    source_name: str = Field(..., description="数据源展示名称，如 🎬-爱奇艺-")
    remarks: Optional[str] = Field(None, description="更新备注，如：更新至第12集")
    type_name: Optional[str] = Field(None, description="分类，如：国产剧、日本动漫")
    year: Optional[str] = Field(None, description="年份")
    area: Optional[str] = Field(None, description="地区")
    media_type: MediaType = Field(default=MediaType.VIDEO, description="媒体形态")

class MediaDetail(SearchItem):
    description: Optional[str] = Field(None, description="剧情简介")
    actors: Optional[str] = Field(None, description="主演演员")
    directors: Optional[str] = Field(None, description="导演")
    routes: List[PlayRoute] = Field(default_factory=list, description="播放线路与选集列表")

class BangumiItem(BaseModel):
    id: int = Field(..., description="Bangumi条目ID")
    name: str = Field(..., description="原名(日文/英文)")
    name_cn: str = Field(..., description="中文译名")
    air_date: Optional[str] = Field(None, description="首播日期")
    air_weekday: int = Field(..., description="放送星期(1-7)")
    score: Optional[float] = Field(None, description="评分")
    cover: Optional[str] = Field(None, description="封面海报")
    summary: Optional[str] = Field(None, description="剧情概述")

class BangumiWeekday(BaseModel):
    weekday_id: int = Field(..., description="星期ID (1-7)")
    weekday_cn: str = Field(..., description="星期名称，如 星期一")
    weekday_en: str = Field(..., description="英文名称，如 Mon")
    items: List[BangumiItem] = Field(default_factory=list, description="当日新番列表")

class SourceInfo(BaseModel):
    key: str
    name: str
    api: str
    detail_url: Optional[str] = None
    is_active: bool = True

class AnimeSourceInfo(BaseModel):
    name: str = Field(..., description="动漫专线源名称")
    description: Optional[str] = Field("", description="说明")
    icon_url: Optional[str] = Field(None, description="图标链接")
    search_url: str = Field(..., description="搜索模板链接")
    tier: int = Field(0, description="优先级等级")

class ParsedStream(BaseModel):
    original_url: str = Field(..., description="原始输入URL")
    stream_url: str = Field(..., description="解析出的有效流媒体播放URL")
    format: str = Field("m3u8", description="流媒体格式: m3u8, mp4, etc.")
    headers: dict[str, str] = Field(default_factory=dict, description="播放该流推荐附加的HTTP请求头(如Referer, User-Agent)")
    is_sniffed: bool = Field(False, description="是否经过网页深度嗅探提取")
    status_code: int = Field(200, description="上游探测响应状态码")
    title: Optional[str] = Field(None, description="网页或流媒体标题")

class ProbeResult(BaseModel):
    url: str
    is_alive: bool
    status_code: int
    latency_ms: float
    content_type: Optional[str] = None
    headers: dict[str, str] = Field(default_factory=dict)

class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: Optional[T] = None

