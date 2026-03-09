import logging
import os
import prometheus_client
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI, Request
from pydantic import BaseModel
from downloader import analyze_video
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, RedirectResponse
from typing import Optional
import subprocess
import threading
import shlex
import re
import os
import yt_dlp
import requests

# Rate limiting
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi.responses import JSONResponse

# slowapi internals changed across versions; provide a stable handler here
def _rate_limit_exceeded_handler(request, exc):
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

# JSON logging
from pythonjsonlogger import jsonlogger

app = FastAPI()

# Allow the frontend origin (Vercel) and the backend domain for testing
app.add_middleware(
    CORSMiddleware,
    # Allow all origins for now so the frontend (Vercel) can call the API.
    # In production restrict this to the real frontend origins.
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# Configure JSON logging
log_handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s')
log_handler.setFormatter(formatter)
root_logger = logging.getLogger()
root_logger.addHandler(log_handler)
root_logger.setLevel(logging.INFO)


# Configure rate limiter (default: 20 requests per minute per IP)
RATE = os.getenv("RATE_LIMIT", "20/minute")
limiter = Limiter(key_func=get_remote_address, default_limits=[RATE])
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Download route limits: combine short-term rate and optional daily quota per IP
DOWNLOAD_RATE_ENV = os.getenv("DOWNLOAD_RATE", "2/minute")
DOWNLOAD_DAILY = os.getenv("DOWNLOAD_DAILY")
if DOWNLOAD_DAILY:
    DOWNLOAD_LIMIT = f"{DOWNLOAD_RATE_ENV};{DOWNLOAD_DAILY}"
else:
    DOWNLOAD_LIMIT = DOWNLOAD_RATE_ENV


# Prometheus metrics
ANALYZE_COUNTER = Counter("streamforge_analyze_requests_total", "Total analyze requests")

class URLRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    format_id: Optional[str] = None
    filename: Optional[str] = None

@app.get("/")
def home():
    return {"message": "StreamForge API running"}


@app.get("/health")
def health():
    """Lightweight health endpoint for monitoring and load balancers."""
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint."""
    return prometheus_client.make_asgi_app()

@app.post("/analyze")
@limiter.limit("10/minute")
def analyze(req: URLRequest, request: Request):
    logging.getLogger("streamforge").info("analyze called", extra={"url": req.url})
    try:
        ANALYZE_COUNTER.inc()
    except Exception:
        pass
    normalized = _normalize_youtube_url(req.url)
    return analyze_video(normalized)


def _sanitize_filename(name: str) -> str:
    if not name:
        return "video"
    name = re.sub(r"[^A-Za-z0-9 _\-\.()]", "", name)
    name = name.strip()
    return name[:200]


def _normalize_youtube_url(url: str) -> str:
    """Normalize common YouTube URL variants to a canonical watch URL.

    Handles:
    - youtu.be short links
    - full watch URLs with extra params
    - /shorts/ URLs
    - urls containing a `v=` query
    If no YouTube id found, returns the original URL.
    """
    if not url:
        return url
    try:
        p = urlparse(url)
        host = (p.hostname or "").lower()
        # short link e.g. https://youtu.be/VIDEO
        if host.endswith("youtu.be"):
            vid = p.path.lstrip("/")
            if vid:
                return f"https://www.youtube.com/watch?v={vid}"

        # youtube full domains
        if host.endswith("youtube.com") or host.endswith("youtube-nocookie.com"):
            # check query param v
            qs = dict([x.split("=", 1) for x in p.query.split("&") if "=" in x]) if p.query else {}
            if "v" in qs:
                return f"https://www.youtube.com/watch?v={qs['v']}"
            # /shorts/<id>
            if p.path.startswith("/shorts/"):
                vid = p.path.split("/", 2)[2] if len(p.path.split("/")) > 2 else None
                if vid:
                    return f"https://www.youtube.com/watch?v={vid}"

        return url
    except Exception:
        return url


def _ffmpeg_stream_generator(input_url: str):
    # Improve HTTP/HLS stability: disable persistent HTTP connections (multiple
    # hosts in a manifest can cause "Cannot reuse HTTP connection for different host")
    # and set a User-Agent so upstream responds correctly.
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        # disable persistent HTTP connections so ffmpeg doesn't try to reuse a
        # single connection for chunks hosted on different domains
        "-http_persistent",
        "0",
        "-user_agent",
        user_agent,
        "-i",
        input_url,
        "-c",
        "copy",
        # Convert ADTS AAC to MP4-friendly stream when needed
        "-bsf:a",
        "aac_adtstoasc",
        "-f",
        "mp4",
        "-movflags",
        "frag_keyframe+empty_moov",
        "pipe:1",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
    # Log ffmpeg stderr in background so we can diagnose failures
    def _log_stderr():
        logger = logging.getLogger("streamforge")
        try:
            while True:
                line = proc.stderr.readline()
                if not line:
                    break
                try:
                    logger.error("ffmpeg: %s", line.decode(errors="ignore").rstrip())
                except Exception:
                    logger.error("ffmpeg: (binary data)")
        except Exception:
            pass

    t = threading.Thread(target=_log_stderr, daemon=True)
    t.start()
    try:
        while True:
            chunk = proc.stdout.read(65536)
            if not chunk:
                break
            yield chunk
    finally:
        try:
            proc.stdout.close()
        except Exception:
            pass
        proc.kill()
        proc.wait()


def _is_manifest_url(url: str) -> bool:
    if not url:
        return False
    low = url.lower()
    # common manifest indicators
    if ".m3u8" in low or "/api/manifest" in low or "playlist/index.m3u8" in low or "manifest.googlevideo.com" in low:
        return True
    # query params sometimes indicate HLS/DASH
    if "mime=" in low and ("mpegurl" in low or "mpegts" in low or "application/vnd.apple.mpegurl" in low):
        return True
    return False


@app.post("/download")
@limiter.limit(DOWNLOAD_LIMIT)
def download(req: DownloadRequest, request: Request):
    logger = logging.getLogger("streamforge")
    logger.info("download called", extra={"url": req.url, "format_id": req.format_id})

    # Use yt-dlp directly here to validate and locate the requested format URL.
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "nocheckcertificate": True,
        "ignoreerrors": True,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
        "js_runtimes": {"deno": {}},
    }
    cookie = os.getenv("COOKIEFILE")
    if cookie:
        ydl_opts["cookiefile"] = cookie

    normalized = _normalize_youtube_url(req.url)
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(normalized, download=False)
    except Exception as e:
        logger.warning("yt-dlp extract failed", extra={"error": str(e)})
        return JSONResponse(status_code=500, content={"detail": "Failed to extract video info"})

    if not info:
        return JSONResponse(status_code=400, content={"detail": "No info extracted"})

    formats = info.get("formats", []) or []

    # select format
    chosen = None
    if req.format_id:
        for f in formats:
            if not f:
                continue
            # match several possible keys
            if str(f.get("format_id") or f.get("format") or f.get("format_id")) == str(req.format_id):
                chosen = f
                break

    if not chosen:
        # prefer progressive
        for ext in ("mp4", "webm", "mkv"):
            chosen = next((f for f in formats if f.get("ext") == ext and f.get("url")), None)
            if chosen:
                break

    if not chosen:
        # fallback to any format with url
        chosen = next((f for f in formats if f.get("url")), None)

    if not chosen or not chosen.get("url"):
        return JSONResponse(status_code=400, content={"detail": "No downloadable format found"})

    src_url = chosen.get("url")

    # if already a progressive file and NOT a manifest URL, proxy it through the server
    # so we can set `Content-Disposition: attachment` and force a Save dialog in browsers.
    if chosen.get("ext") in ("mp4", "webm", "mkv") and not _is_manifest_url(src_url):
        logger.info("chosen progressive format", extra={"ext": chosen.get("ext"), "src_url": src_url})
        try:
            upstream = requests.get(src_url, stream=True, timeout=15, headers={"User-Agent": ydl_opts["http_headers"]["User-Agent"], "Referer": "https://www.youtube.com/"})
        except Exception as e:
            logger.warning("upstream fetch failed", extra={"error": str(e)})
            return JSONResponse(status_code=502, content={"detail": "Failed to fetch upstream media"})

        logger.info("upstream response", extra={"status_code": getattr(upstream, "status_code", None), "headers": dict(upstream.headers)})
        content_type = upstream.headers.get("Content-Type", "application/octet-stream")
        content_length = upstream.headers.get("Content-Length")
        def _proxy_gen():
            try:
                for chunk in upstream.iter_content(chunk_size=65536):
                    if chunk:
                        yield chunk
            finally:
                try:
                    upstream.close()
                except Exception:
                    pass

        headers = {"Content-Disposition": f'attachment; filename="{req.filename or _sanitize_filename(info.get("title"))}.mp4"'}
        if content_length:
            headers["Content-Length"] = content_length
        return StreamingResponse(_proxy_gen(), media_type=content_type, headers=headers)

    # otherwise stream via ffmpeg (handles HLS/DASH manifests and fragmented streams)
    title = info.get("title")
    filename = req.filename or f"{_sanitize_filename(title)}.mp4"
    generator = _ffmpeg_stream_generator(src_url)
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(generator, media_type="video/mp4", headers=headers)


@app.get("/download")
@limiter.limit(DOWNLOAD_LIMIT)
def download_get(url: str, format_id: Optional[str] = None, filename: Optional[str] = None, request: Request = None):
    # Provide a simple GET endpoint so the frontend can open a URL in a new tab.
    body = DownloadRequest(url=url, format_id=format_id, filename=filename)
    return download(body, request)


from urllib.parse import urlparse


@app.api_route("/proxy", methods=["GET", "HEAD", "OPTIONS"])
@limiter.limit("30/minute")
def proxy(url: str, request: Request):
    """Proxy limited external resources (manifests/segments) through the server.

    Only allow known video hosts to avoid open proxy abuse.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return JSONResponse(status_code=400, content={"detail": "Invalid URL"})

    host = (parsed.hostname or "").lower()
    # Allow common YouTube-related hosts (manifest/segments, static assets, short links)
    allowed_suffixes = (
        "googlevideo.com",
        "youtube.com",
        "ytimg.com",
        "youtu.be",
        "youtube-nocookie.com",
        "youtube.googleapis.com",
    )
    if not any(host.endswith(s) for s in allowed_suffixes):
        return JSONResponse(status_code=403, content={"detail": "Forbidden host"})

    # Forward relevant client headers (Range etc.) to upstream to support partial requests.
    # Request uncompressed responses from upstream to avoid decoding mismatches
    forward_headers = {
        "User-Agent": "Mozilla/5.0 (compatible; StreamForge/1.0)",
        "Accept-Encoding": "identity",
    }
    incoming_range = request.headers.get("range")
    if incoming_range:
        forward_headers["Range"] = incoming_range
    incoming_referer = request.headers.get("referer") or request.headers.get("referrer")
    if incoming_referer:
        forward_headers["Referer"] = incoming_referer

    # Handle CORS preflight explicitly so browsers can validate Range requests
    if request.method == "OPTIONS":
        cors_headers = {}
        origin = request.headers.get("origin")
        if origin:
            cors_headers["Access-Control-Allow-Origin"] = origin
            cors_headers["Vary"] = "Origin"
        else:
            cors_headers["Access-Control-Allow-Origin"] = "*"
        cors_headers["Access-Control-Allow-Methods"] = "GET, HEAD, OPTIONS"
        cors_headers["Access-Control-Allow-Headers"] = "Range, Accept, Origin, Content-Type"
        cors_headers["Access-Control-Expose-Headers"] = "Content-Range, Accept-Ranges, Content-Length, Content-Encoding"
        return JSONResponse(status_code=204, content=None, headers=cors_headers)

    try:
        upstream = requests.get(url, stream=True, timeout=15, headers=forward_headers)
    except Exception as e:
        logging.getLogger("streamforge").warning("proxy upstream failed", extra={"error": str(e)})
        return JSONResponse(status_code=502, content={"detail": "Upstream fetch failed"})

    content_type = upstream.headers.get("Content-Type", "application/octet-stream")
    def _gen():
        try:
            for chunk in upstream.iter_content(chunk_size=65536):
                if chunk:
                    yield chunk
        finally:
            try:
                upstream.close()
            except Exception:
                pass

    # Preserve important headers and the upstream status code so the browser
    # can correctly handle range requests (206 Partial Content) and streaming
    resp_headers = {}
    for h in ("Content-Length", "Content-Range", "Accept-Ranges", "Cache-Control"):
        v = upstream.headers.get(h)
        if v:
            resp_headers[h] = v

    # Ensure Content-Type is present
    if content_type:
        resp_headers["Content-Type"] = content_type

    # Add cross-origin headers so the browser can load segmented media
    origin = request.headers.get("origin")
    if origin:
        resp_headers["Access-Control-Allow-Origin"] = origin
        resp_headers["Vary"] = "Origin"
    else:
        resp_headers["Access-Control-Allow-Origin"] = "*"

    # Allow the resource to be used cross-origin by media elements
    resp_headers["Cross-Origin-Resource-Policy"] = "cross-origin"
    # Expose range-related headers to the browser
    resp_headers["Access-Control-Expose-Headers"] = "Content-Range, Accept-Ranges, Content-Length, Content-Encoding"
    # Allow credentials optionally if environment enables it (default: no)
    if os.getenv("ALLOW_CREDENTIALS", "false").lower() in ("1", "true", "yes"):
        resp_headers["Access-Control-Allow-Credentials"] = "true"

    status_code = getattr(upstream, "status_code", 200) or 200

    return StreamingResponse(_gen(), status_code=status_code, media_type=content_type, headers=resp_headers)