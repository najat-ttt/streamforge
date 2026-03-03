from fastapi import FastAPI
from pydantic import BaseModel
from downloader import analyze_video
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class URLRequest(BaseModel):
    url: str


@app.get("/")
def home():
    return {"message": "StreamForge API running (stream mode)"}


@app.post("/analyze")
def analyze(req: URLRequest):
    return analyze_video(req.url)