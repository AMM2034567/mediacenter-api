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

settings = Settings()
