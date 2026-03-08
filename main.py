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
    allow_origins=[
        "https://streamforge-frontend.vercel.app",
        "https://streamforge-naj.duckdns.org",
    ],
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
    return analyze_video(req.url)


def _sanitize_filename(name: str) -> str:
    if not name:
        return "video"
    name = re.sub(r"[^A-Za-z0-9 _\-\.()]", "", name)
    name = name.strip()
    return name[:200]


def _ffmpeg_stream_generator(input_url: str):
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        input_url,
        "-c",
        "copy",
        "-f",
        "mp4",
        "-movflags",
        "frag_keyframe+empty_moov",
        "pipe:1",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(req.url, download=False)
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

    # if already a progressive file, proxy it through the server so we can
    # set `Content-Disposition: attachment` and force a Save dialog in browsers.
    if chosen.get("ext") in ("mp4", "webm", "mkv"):
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

    # otherwise stream via ffmpeg
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