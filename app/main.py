import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.sources.manager import SourceManager
from app.api.v1.search import router as search_router
from app.api.v1.detail import router as detail_router
from app.api.v1.source import router as source_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load sources in background so server starts immediately
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    asyncio.create_task(SourceManager.get_instance().reload_from_remote())
    yield
    # Shutdown
    logger.info("Shutting down...")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="聚合多媒体中心后台 API 服务 (聚合影视/番剧/多源串流)",
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

# Register API Routers
app.include_router(search_router, prefix="/api/v1")
app.include_router(detail_router, prefix="/api/v1")
app.include_router(source_router, prefix="/api/v1")

@app.get("/", tags=["Health"])
async def root():
    return {
        "status": "online",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "sources_count": len(SourceManager.get_instance().list_sources())
    }

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}

from fastapi import Request

@app.api_route("/{path_name:path}", methods=["GET", "POST", "HEAD"], include_in_schema=False)
async def catch_all(request: Request, path_name: str):
    return {
        "status": "debug_path",
        "path_name": path_name,
        "url_path": request.url.path,
        "scope_path": request.scope.get("path"),
        "root_path": request.scope.get("root_path"),
        "headers": dict(request.headers),
        "query_params": dict(request.query_params)
    }
