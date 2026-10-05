from typing import List, Optional
from pydantic import BaseModel, Field

class MusicSong(BaseModel):
    id: str = Field(..., description="歌曲唯一ID，如 netease:12345 或 qq:0039MnYb0qxYhV")
    name: str = Field(..., description="歌曲标题")
    artist: str = Field(..., description="歌手名称")
    album: Optional[str] = Field(None, description="专辑名称")
    cover: Optional[str] = Field(None, description="封面图片地址")
    duration: int = Field(0, description="时长（秒）")
    platform: str = Field("netease", description="平台：netease 或 qq")
    mid: Optional[str] = Field(None, description="QQ 音乐专属 MID")
    play_url: Optional[str] = Field(None, description="播放音频直链")
    lrc: Optional[str] = Field(None, description="LRC 同步歌词")

class MusicRank(BaseModel):
    id: str = Field(..., description="榜单ID")
    name: str = Field(..., description="榜单名称")
    description: Optional[str] = Field(None, description="榜单描述")
    cover: Optional[str] = Field(None, description="榜单封面")
    update_frequency: Optional[str] = Field("每日更新", description="更新频率")
    songs: List[MusicSong] = Field(default_factory=list, description="榜单歌曲列表")
