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

class SourceInfo(BaseModel):
    key: str
    name: str
    api: str
    detail_url: Optional[str] = None
    is_active: bool = True

class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: Optional[T] = None
