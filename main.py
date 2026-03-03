from fastapi import FastAPI
from pydantic import BaseModel
from downloader import analyze_video
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()


# =========================
# CORS (IMPORTANT FOR VERCEL)
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # later restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# MODELS
# =========================
class URLRequest(BaseModel):
    url: str


# =========================
# ROUTES
# =========================
@app.get("/")
def home():
    return {
        "message": "StreamForge API running (Stream Mode)",
        "status": "ok"
    }


@app.post("/analyze")
def analyze(req: URLRequest):
    return analyze_video(req.url)