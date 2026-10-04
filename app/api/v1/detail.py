import logging
from typing import Optional
from fastapi import APIRouter, Query, HTTPException
import httpx

from app.models.media import MediaDetail, ApiResponse
from app.sources.manager import SourceManager
from app.sources.maccms import MacCMSDriver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/detail", tags=["Detail"])

@router.get("", response_model=ApiResponse[MediaDetail])
async def get_media_detail(
    id: Optional[str] = Query(None, description="标准媒体复合ID，例如：maccms:cj.lzcaiji.com:28965"),
    source: Optional[str] = Query(None, description="数据源Key，若传了id则可不传"),
    vod_id: Optional[str] = Query(None, description="资源ID，若传了id则可不传")
):
    source_key = source
    target_vod_id = vod_id
    
    # Parse composite id if provided
    if id:
        parts = id.split(":")
        if len(parts) >= 3:
            # maccms:site_key:vod_id
            source_key = parts[1]
            target_vod_id = ":".join(parts[2:])
        else:
            raise HTTPException(status_code=400, detail="Invalid composite id format. Expected 'maccms:{source_key}:{vod_id}'")
            
    if not source_key or not target_vod_id:
        raise HTTPException(status_code=400, detail="Must provide either 'id' or both 'source' and 'vod_id'")
        
    source_mgr = SourceManager.get_instance()
    src = source_mgr.get_source(source_key)
    if not src:
        raise HTTPException(status_code=404, detail=f"Source key '{source_key}' not found in active registry")
        
    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    ) as client:
        detail = await MacCMSDriver.detail(
            client=client,
            site_key=src.key,
            site_name=src.name,
            api_url=src.api,
            vod_id=target_vod_id
        )
        
    if not detail:
        raise HTTPException(status_code=404, detail="Media details not found or upstream error")
        
    return ApiResponse(code=0, message="ok", data=detail)
