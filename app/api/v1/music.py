from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException

from app.models.media import ApiResponse
from app.models.music import MusicSong, MusicRank
from app.sources.music_manager import MusicManager

router = APIRouter(prefix="/music", tags=["Music Center"])

@router.get("/ranks", response_model=ApiResponse[List[MusicRank]], summary="获取音乐推荐与热门榜单列表")
async def get_music_ranks():
    mgr = MusicManager.get_instance()
    ranks = mgr.get_ranks()
    return ApiResponse(data=ranks)

@router.get("/rank/{rank_id}", response_model=ApiResponse[List[MusicSong]], summary="获取指定榜单歌曲列表")
async def get_rank_songs(
    rank_id: str,
    limit: int = Query(50, ge=1, le=100, description="返回歌曲数量")
):
    mgr = MusicManager.get_instance()
    songs = await mgr.get_rank_songs(rank_id=rank_id, limit=limit)
    return ApiResponse(data=songs)

@router.get("/search", response_model=ApiResponse[List[MusicSong]], summary="全网音乐关键词搜索")
async def search_music(
    kw: str = Query(..., description="搜索关键词，如歌曲名、歌手"),
    limit: int = Query(30, ge=1, le=50, description="返回数量")
):
    mgr = MusicManager.get_instance()
    songs = await mgr.search_songs(keyword=kw, limit=limit)
    return ApiResponse(data=songs)

@router.get("/song/{song_id}", response_model=ApiResponse[MusicSong], summary="获取单曲完整详情（含播放直链与LRC歌词）")
async def get_song_detail(song_id: str):
    mgr = MusicManager.get_instance()
    song = await mgr.get_song_detail(song_id)
    if not song:
        raise HTTPException(status_code=404, detail="未找到该歌曲详情")
    return ApiResponse(data=song)

@router.get("/song/{song_id}/url", response_model=ApiResponse[dict], summary="快速获取歌曲播放直链")
async def get_song_play_url(song_id: str):
    mgr = MusicManager.get_instance()
    url = await mgr.get_song_play_url(song_id)
    if not url:
        raise HTTPException(status_code=404, detail="无法解析该歌曲播放直链")
    return ApiResponse(data={"url": url})

@router.get("/song/{song_id}/lrc", response_model=ApiResponse[dict], summary="获取歌曲同步LRC时间轴歌词")
async def get_song_lrc(song_id: str):
    mgr = MusicManager.get_instance()
    lrc = await mgr.get_song_lrc(song_id)
    return ApiResponse(data={"lrc": lrc or ""})
