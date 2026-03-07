import logging
import os
import prometheus_client
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI, Request
from pydantic import BaseModel
from downloader import analyze_video
from fastapi.middleware.cors import CORSMiddleware

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
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


# Prometheus metrics
ANALYZE_COUNTER = Counter("streamforge_analyze_requests_total", "Total analyze requests")

class URLRequest(BaseModel):
    url: str

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