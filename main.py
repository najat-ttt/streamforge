from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from downloader import get_stream_url
from pydantic import BaseModel

app = FastAPI()

class URLRequest(BaseModel):
    url: str


@app.post("/analyze")
def analyze(req: URLRequest):
    return get_stream_url(req.url)


@app.get("/stream")
def stream(url: str):
    import requests

    r = requests.get(url, stream=True)

    return StreamingResponse(
        r.iter_content(chunk_size=1024 * 1024),
        media_type="video/mp4"
    )