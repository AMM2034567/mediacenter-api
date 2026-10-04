import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "MediaCenter Backend"
    APP_VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = int(os.getenv("PORT", 7860))  # Hugging Face Spaces requires port 7860
    
    # 默认订阅源：LunaTV 精简禁18配置 (每日自动更新)
    DEFAULT_SOURCE_URL: str = os.getenv(
        "DEFAULT_SOURCE_URL",
        "https://raw.githubusercontent.com/hafrey1/LunaTV-config/refs/heads/main/jin18.txt"
    )
    
    # 上游 API 请求超时时间 (秒)
    UPSTREAM_TIMEOUT: float = 6.0
    
    # 搜索缓存时间 (秒)
    SEARCH_CACHE_TTL: int = 1800  # 30分钟
    
    # 源配置缓存时间 (秒)
    SOURCE_CACHE_TTL: int = 43200  # 12小时

    # 安全配置：API 密钥鉴权 (可由环境变量 API_KEY 覆盖)
    API_KEY: str = os.getenv("API_KEY", "pXrftYC2bd")

    # 是否开启 Swagger 文档界面 (生产环境可通过 ENABLE_DOCS=false 关闭)
    ENABLE_DOCS: bool = os.getenv("ENABLE_DOCS", "true").lower() in ("true", "1")

settings = Settings()
