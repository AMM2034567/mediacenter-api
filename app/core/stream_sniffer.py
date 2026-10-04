import re
import base64
import time
import logging
from typing import Optional, Dict, Tuple
from urllib.parse import urlparse, urljoin, unquote
import httpx

from app.models.media import ParsedStream, ProbeResult

logger = logging.getLogger(__name__)

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

STREAM_EXT_PATTERN = re.compile(
    r"https?://[^\s\"'<>\\]+?\.(?:m3u8|mp4)(?:\?[^\s\"'<>\\]*)?",
    re.IGNORECASE
)

VAR_URL_PATTERN = re.compile(
    r"(?:var|let|const)?\s*(?:url|urls|video|src|play_url|v_url|playUrl|main)\s*[:=]\s*[\"']([^\"']+)[\"']",
    re.IGNORECASE
)

JSON_URL_PATTERN = re.compile(
    r"[\"']url[\"']\s*:\s*[\"']([^\"']+)[\"']",
    re.IGNORECASE
)

IFRAME_PATTERN = re.compile(
    r"<iframe[^>]+src=[\"']([^\"']+)[\"']",
    re.IGNORECASE
)


def is_direct_stream_url(url: str) -> bool:
    """Checks whether the URL path points directly to an .m3u8 or .mp4 file."""
    try:
        path = urlparse(url).path.lower()
        return path.endswith(".m3u8") or path.endswith(".mp4") or ".m3u8" in path or ".mp4" in path
    except Exception:
        return False


def derive_stream_headers(url: str, custom_referer: Optional[str] = None) -> Dict[str, str]:
    """
    Derives anti-hotlinking headers (Referer, User-Agent) tailored for playback.
    """
    try:
        parsed = urlparse(url)
        referer = custom_referer or f"{parsed.scheme}://{parsed.netloc}/"
        return {
            "User-Agent": DEFAULT_UA,
            "Referer": referer,
            "Origin": f"{parsed.scheme}://{parsed.netloc}",
        }
    except Exception:
        return {"User-Agent": DEFAULT_UA}


def extract_stream_from_text(text: str, base_url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extracts stream URL from raw HTML, JavaScript, or text.
    Returns (stream_url, iframe_url).
    """
    if not text:
        return None, None

    # 1. Direct playlist verification
    if "#EXTM3U" in text:
        return base_url, None

    # 2. Check for direct stream URLs inside text
    matches = STREAM_EXT_PATTERN.findall(text)
    for m in matches:
        clean_url = m.replace(r"\/", "/")
        if clean_url.startswith("http"):
            return clean_url, None

    # 3. Check for player variable definitions (e.g. var url = '...')
    for pattern in (VAR_URL_PATTERN, JSON_URL_PATTERN):
        for candidate in pattern.findall(text):
            candidate = candidate.strip().replace(r"\/", "/")
            # URL unescape check
            if "%2F" in candidate or "%3A" in candidate:
                candidate = unquote(candidate)
            if candidate.startswith("http") and (".m3u8" in candidate or ".mp4" in candidate):
                return candidate, None
            # Check relative URL
            if (candidate.startswith("/") or candidate.endswith(".m3u8") or candidate.endswith(".mp4")) and not candidate.startswith("http"):
                full_resolved = urljoin(base_url, candidate)
                return full_resolved, None

    # 4. Check for Base64 encoded streams
    b64_candidates = re.findall(r"[\"']([A-Za-z0-9+/=]{24,})[\"']", text)
    for b64_str in b64_candidates:
        try:
            decoded = base64.b64decode(b64_str).decode("utf-8", errors="ignore")
            if "http" in decoded and (".m3u8" in decoded or ".mp4" in decoded):
                b64_match = STREAM_EXT_PATTERN.search(decoded)
                if b64_match:
                    return b64_match.group(0), None
        except Exception:
            continue

    # 5. Check for iframe
    iframe_match = IFRAME_PATTERN.search(text)
    if iframe_match:
        iframe_src = iframe_match.group(1).strip()
        full_iframe = urljoin(base_url, iframe_src)
        return None, full_iframe

    return None, None


async def probe_stream(url: str, timeout: float = 5.0) -> ProbeResult:
    """
    Rapidly probes a video stream or URL to check latency and connectivity.
    """
    start_time = time.time()
    headers = derive_stream_headers(url)
    headers["Range"] = "bytes=0-1024"  # Probe first 1KB only for minimal bandwidth

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
            resp = await client.get(url)
            latency = (time.time() - start_time) * 1000.0
            is_alive = resp.status_code in (200, 206, 302, 304)
            return ProbeResult(
                url=str(resp.url),
                is_alive=is_alive,
                status_code=resp.status_code,
                latency_ms=round(latency, 2),
                content_type=resp.headers.get("content-type"),
                headers=dict(resp.headers)
            )
    except Exception as e:
        latency = (time.time() - start_time) * 1000.0
        logger.debug(f"Stream probe failed for {url}: {e}")
        return ProbeResult(
            url=url,
            is_alive=False,
            status_code=500,
            latency_ms=round(latency, 2),
            content_type=None,
            headers={}
        )


async def parse_and_sniff_stream(url: str, timeout: float = 7.0) -> ParsedStream:
    """
    Parses and sniffs any video link (direct m3u8/mp4 or web player iframe)
    and extracts the actual pure streaming URL with required headers.
    """
    cleaned_url = url.strip()
    headers = derive_stream_headers(cleaned_url)

    # 1. Fast path: If it's already a direct m3u8 or mp4
    if is_direct_stream_url(cleaned_url):
        fmt = "mp4" if ".mp4" in cleaned_url.lower() else "m3u8"
        return ParsedStream(
            original_url=cleaned_url,
            stream_url=cleaned_url,
            format=fmt,
            headers=headers,
            is_sniffed=False,
            status_code=200
        )

    # 2. Deep sniffing path: fetch webpage content
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
        try:
            resp = await client.get(cleaned_url)
            final_page_url = str(resp.url)
            text_content = resp.text

            # Extract from first page
            stream_url, iframe_url = extract_stream_from_text(text_content, final_page_url)

            # If iframe found and no stream yet, follow iframe
            if not stream_url and iframe_url:
                try:
                    iframe_headers = derive_stream_headers(iframe_url, custom_referer=final_page_url)
                    iframe_resp = await client.get(iframe_url, headers=iframe_headers)
                    stream_url, _ = extract_stream_from_text(iframe_resp.text, str(iframe_resp.url))
                except Exception as ie:
                    logger.debug(f"Iframe sniffing failed for {iframe_url}: {ie}")

            if stream_url:
                fmt = "mp4" if ".mp4" in stream_url.lower() else "m3u8"
                stream_headers = derive_stream_headers(stream_url, custom_referer=final_page_url)
                return ParsedStream(
                    original_url=cleaned_url,
                    stream_url=stream_url,
                    format=fmt,
                    headers=stream_headers,
                    is_sniffed=True,
                    status_code=200
                )

        except Exception as e:
            logger.warning(f"Failed to sniff stream from {cleaned_url}: {e}")

    # Fallback to original url
    fmt = "mp4" if ".mp4" in cleaned_url.lower() else "m3u8"
    return ParsedStream(
        original_url=cleaned_url,
        stream_url=cleaned_url,
        format=fmt,
        headers=headers,
        is_sniffed=False,
        status_code=200
    )
