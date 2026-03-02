import yt_dlp
import tempfile
import uuid
import threading
import queue
import os

# Move temp away from C
tempfile.tempdir = "E:/temp"

downloads = {}

# CONFIG
MAX_PARALLEL_DOWNLOADS = 3

download_queue = queue.Queue()


# =========================
# ANALYZE
# =========================
def analyze_video(url):
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    # PLAYLIST
    if info.get('_type') == 'playlist':
        videos = []

        for entry in info.get("entries", []):
            if not entry:
                continue

            vid = entry.get("id")
            if not vid:
                continue

            videos.append({
                "title": entry.get("title"),
                "url": f"https://www.youtube.com/watch?v={vid}",
            })

        return {
            "type": "playlist",
            "title": info.get("title"),
            "videos": videos
        }

    # SINGLE VIDEO (GET FULL DATA AGAIN)
    ydl_opts_full = {
        'quiet': True,
        'skip_download': True
    }

    with yt_dlp.YoutubeDL(ydl_opts_full) as ydl:
        info = ydl.extract_info(url, download=False)

    formats = []
    seen = set()

    for f in info.get('formats', []):
        height = f.get('height')
        if not height:
            continue

        # only include formats that have video
        if f.get("vcodec") == "none":
            continue

        key = (height, f.get("ext"))

        # avoid duplicates (same resolution)
        if key in seen:
            continue
        seen.add(key)

        formats.append({
            "format_id": f.get("format_id"),
            "quality": f"{height}p",
            "filesize": f.get("filesize"),
            "ext": f.get("ext"),
        })

    # sort by quality descending
    formats = sorted(formats, key=lambda x: int(x["quality"].replace("p", "")), reverse=True)

    return {
        "type": "video",
        "title": info.get("title"),
        "thumbnail": info.get("thumbnail"),
        "formats": formats
    }


# =========================
# WORKER
# =========================
def worker():
    while True:
        task = download_queue.get()

        if task is None:
            break

        url, format_id, download_id = task

        try:
            run_download(url, format_id, download_id)
        finally:
            download_queue.task_done()


# Start workers
for _ in range(MAX_PARALLEL_DOWNLOADS):
    threading.Thread(target=worker, daemon=True).start()


# =========================
# DOWNLOAD CORE
# =========================
def run_download(url, format_id, download_id):

    def progress_hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 1
            downloaded = d.get('downloaded_bytes', 0)

            percent = int(downloaded * 100 / total)

            downloads[download_id]["progress"] = percent
            downloads[download_id]["status"] = "downloading"

        elif d['status'] == 'finished':
            downloads[download_id]["status"] = "processing"

    try:
        downloads[download_id]["status"] = "downloading"

        ydl_opts = {
            'format': f"{format_id}+bestaudio/best",
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'merge_output_format': 'mp4',
            'progress_hooks': [progress_hook],
            'noplaylist': True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # final file path
            filename = ydl.prepare_filename(info)

            # ensure mp4 after merge
            if not filename.endswith(".mp4"):
                filename = os.path.splitext(filename)[0] + ".mp4"

            downloads[download_id]["filename"] = filename

        downloads[download_id]["status"] = "finished"
        downloads[download_id]["progress"] = 100

    except Exception as e:
        downloads[download_id]["status"] = "error"
        downloads[download_id]["error"] = str(e)


# =========================
# ADD TO QUEUE
# =========================
def download_video(url, format_id):
    download_id = str(uuid.uuid4())

    downloads[download_id] = {
        "status": "queued",
        "progress": 0,
        "filename": None
    }

    download_queue.put((url, format_id, download_id))

    return download_id