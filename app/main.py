import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.security import verify_api_key
from app.sources.manager import SourceManager
from app.sources.live_manager import LiveManager
from app.api.v1.search import router as search_router
from app.api.v1.detail import router as detail_router
from app.api.v1.source import router as source_router
from app.api.v1.bangumi import router as bangumi_router
from app.api.v1.category import router as category_router
from app.api.v1.parse import router as parse_router
from app.api.v1.live import router as live_router
from app.api.v1.music import router as music_router
from app.api.v1.charts import router as charts_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load video sources and IPTV/Radio sources in background
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    asyncio.create_task(SourceManager.get_instance().reload_from_remote())
    asyncio.create_task(LiveManager.get_instance().reload_all_sources())
    yield
    # Shutdown
    logger.info("Shutting down...")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="聚合多媒体中心后台 API 服务 (安全凭证保护版)",
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.ENABLE_DOCS else None,
    lifespan=lifespan
)

# Enable CORS for all clients (Web/Mobile)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers with API Key Authentication
app.include_router(search_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)])
app.include_router(detail_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)])
app.include_router(source_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)])
app.include_router(bangumi_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)])
app.include_router(category_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)])
app.include_router(parse_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)])
app.include_router(live_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)])
app.include_router(music_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)])
app.include_router(charts_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)])


@app.get("/", tags=["Health"])
async def root():
    return {
        "status": "online",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "sources_count": len(SourceManager.get_instance().list_sources()),
        "live_channels_count": len(LiveManager.get_instance().list_channels()),
    }

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}
