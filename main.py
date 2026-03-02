from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict
from downloader import analyze_video, download_video, downloads
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
import tempfile

os.makedirs("downloads", exist_ok=True)
os.makedirs("/tmp", exist_ok=True)
tempfile.tempdir = "/tmp"

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


class DownloadRequest(BaseModel):
    url: str
    format_id: str


@app.get("/")
def home():
    return {"message": "StreamForge API is running"}


@app.post("/analyze")
def analyze(req: URLRequest):
    return analyze_video(req.url)


@app.post("/download", response_model=Dict[str, str])
def download(req: DownloadRequest):
    download_id = download_video(req.url, req.format_id)

    return {
        "download_id": download_id,
        "status": "started"
    }


@app.get("/status/{download_id}")
def get_status(download_id: str):
    if download_id not in downloads:
        return {"error": "Invalid download ID"}

    return downloads[download_id]


@app.get("/file/{download_id}")
def get_file(download_id: str):
    if download_id not in downloads:
        return {"error": "Invalid ID"}

    file_path = downloads[download_id].get("filename")

    if not file_path or not os.path.exists(file_path):
        return {"error": "File not ready"}

    return FileResponse(
        file_path,
        filename=os.path.basename(file_path),
        media_type="application/octet-stream"
    )