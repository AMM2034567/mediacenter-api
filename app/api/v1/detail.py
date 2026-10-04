import logging
import asyncio
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
import httpx

from app.models.media import MediaDetail, ApiResponse, PlayRoute
from app.sources.manager import SourceManager
from app.sources.maccms import MacCMSDriver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/detail", tags=["Detail"])

TOP_BACKUP_SOURCES = ["dyttzyapi.com", "cj.lzcaiji.com", "bfzy.tv", "ffzyapi.com", "ikunzy.com"]

@router.get("", response_model=ApiResponse[MediaDetail])
async def get_media_detail(
    id: Optional[str] = Query(None, description="标准媒体复合ID，例如：maccms:cj.lzcaiji.com:28965"),
    source: Optional[str] = Query(None, description="数据源Key，若传了id则可不传"),
    vod_id: Optional[str] = Query(None, description="资源ID，若传了id则可不传"),
    title: Optional[str] = Query(None, description="媒体名称，用于容灾备份与多源线路聚合")
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
    
    detail: Optional[MediaDetail] = None
    
    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    ) as client:
        if src:
            try:
                detail = await MacCMSDriver.detail(
                    client=client,
                    site_key=src.key,
                    site_name=src.name,
                    api_url=src.api,
                    vod_id=target_vod_id
                )
            except Exception as e:
                logger.warning(f"Failed to fetch detail from primary source {src.key}: {e}")
                
        search_title = (title or (detail.title if detail else "")).strip()
        
        # 1. Failover recovery if primary source failed or returned no routes
        if (not detail or not detail.routes) and search_title:
            logger.info(f"Primary source {source_key} failed or has no routes, attempting failover for: {search_title}")
            for backup_key in TOP_BACKUP_SOURCES:
                if backup_key == source_key:
                    continue
                backup_src = source_mgr.get_source(backup_key)
                if not backup_src:
                    continue
                try:
                    candidates = await MacCMSDriver.search(
                        client=client,
                        site_key=backup_src.key,
                        site_name=backup_src.name,
                        api_url=backup_src.api,
                        keyword=search_title
                    )
                    matching = [c for c in candidates if c.title.strip() == search_title or search_title in c.title]
                    if matching:
                        match_id = matching[0].id.split(":")[-1]
                        detail = await MacCMSDriver.detail(
                            client=client,
                            site_key=backup_src.key,
                            site_name=backup_src.name,
                            api_url=backup_src.api,
                            vod_id=match_id
                        )
                        if detail and detail.routes:
                            logger.info(f"Recovered detail from backup source: {backup_src.name}")
                            break
                except Exception as e:
                    logger.debug(f"Backup source search failed: {e}")
                    
        # 2. Enrich with backup routes from top alternative sources if routes count <= 2
        if detail and search_title and len(detail.routes) <= 2:
            existing_route_names = {r.name.lower() for r in detail.routes}
            backup_candidates = [k for k in TOP_BACKUP_SOURCES if k != detail.source_key][:2]
            
            async def fetch_backup_routes(b_key: str) -> List[PlayRoute]:
                b_src = source_mgr.get_source(b_key)
                if not b_src:
                    return []
                try:
                    items = await MacCMSDriver.search(
                        client=client,
                        site_key=b_src.key,
                        site_name=b_src.name,
                        api_url=b_src.api,
                        keyword=search_title
                    )
                    exact = [it for it in items if it.title.strip() == search_title]
                    if not exact:
                        return []
                    v_id = exact[0].id.split(":")[-1]
                    b_detail = await MacCMSDriver.detail(
                        client=client,
                        site_key=b_src.key,
                        site_name=b_src.name,
                        api_url=b_src.api,
                        vod_id=v_id
                    )
                    if not b_detail:
                        return []
                    out_routes: List[PlayRoute] = []
                    for r in b_detail.routes:
                        clean_src = b_src.name.replace('🎬', '').strip()
                        tagged_name = f"[{clean_src}] {r.name}"
                        if tagged_name.lower() not in existing_route_names:
                            out_routes.append(PlayRoute(name=tagged_name, episodes=r.episodes))
                    return out_routes
                except Exception:
                    return []
                    
            route_batches = await asyncio.gather(*[fetch_backup_routes(k) for k in backup_candidates], return_exceptions=True)
            for batch in route_batches:
                if isinstance(batch, list):
                    detail.routes.extend(batch)
                    
    if not detail:
        raise HTTPException(status_code=404, detail="Media details not found or upstream error")
        
    return ApiResponse(code=0, message="ok", data=detail)
