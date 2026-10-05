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

    # Bangumi 番组计划时刻表 API 与镜像
    BANGUMI_API_URL: str = os.getenv("BANGUMI_API_URL", "https://api.bgm.tv/calendar")
    BANGUMI_MIRROR_URL: str = os.getenv("BANGUMI_MIRROR_URL", "https://bangumi.vip/calendar")
    BANGUMI_CACHE_TTL: int = 43200  # 12小时

    # 动漫专属专线源订阅
    ANIME_SOURCE_URL: str = os.getenv(
        "ANIME_SOURCE_URL",
        "https://sub.creamycake.org/v1/css1.json"
    )

    # IPTV 电视直播订阅源列表 (精选国内高稳定性公网 CDN 源，规避移动内网失效组播/单播源)
    IPTV_SOURCE_URLS: list[str] = [
        "https://raw.githubusercontent.com/vbskycn/iptv/refs/heads/master/tv/iptv4.m3u",
        "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u",
    ]

    # 广播电台 (FM/音频广播) 订阅源列表
    RADIO_SOURCE_URLS: list[str] = [
        "https://raw.githubusercontent.com/fanmingming/live/main/radio/m3u/index.m3u",
    ]

    # GitHub CDN 加速镜像前缀 (用于国内网络环境突破 GitHub Raw 访问限制)
    GITHUB_CDN_PREFIXES: list[str] = [
        "",  # 直连优先
        "https://ghproxy.net/",
        "https://raw.gitmirror.com/",
    ]

    # 直播与广播订阅缓存时间 (秒)
    LIVE_CACHE_TTL: int = 21600  # 6小时

    # 安全配置：API 密钥鉴权 (可由环境变量 API_KEY 覆盖)
    API_KEY: str = os.getenv("API_KEY", "pXrftYC2bd")

    # 是否开启 Swagger 文档界面 (生产环境可通过 ENABLE_DOCS=false 关闭)
    ENABLE_DOCS: bool = os.getenv("ENABLE_DOCS", "true").lower() in ("true", "1")

settings = Settings()

