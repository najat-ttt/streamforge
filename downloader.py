import os
import random
import time
import logging
import yt_dlp


logger = logging.getLogger("downloader")


def analyze_video(url):
    """Analyze a YouTube URL and return metadata and direct stream URLs.

    Supports optional environment variables:
    - COOKIEFILE: path to cookies.txt for authenticated extraction
    - PROXY_LIST: comma-separated list of HTTP proxies to rotate (e.g. http://1.2.3.4:8080)
    """
    COOKIEFILE = os.getenv("COOKIEFILE")
    PROXY_LIST = os.getenv("PROXY_LIST")

    proxies = [p.strip() for p in (PROXY_LIST or "").split(",") if p.strip()]

    # Base options
    base_opts = {
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
        # Force a JS runtime for yt-dlp EJS challenge solving
        # yt-dlp expects a dict of runtimes -> config (not a plain string)
        "js_runtimes": {"deno": {}},
    }

    if COOKIEFILE:
        base_opts["cookiefile"] = COOKIEFILE
        logger.info("Using cookiefile", extra={"cookiefile": COOKIEFILE})

    # Try to extract info with a small retry/backoff loop
    attempts = 0
    max_attempts = 3
    last_err = None

    while attempts < max_attempts:
        opts = base_opts.copy()

        if proxies:
            chosen = random.choice(proxies)
            opts["proxy"] = chosen
            logger.info("Using proxy for extraction", extra={"proxy": chosen})

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if not info:
                return {"error": "Failed to fetch video info (YouTube blocked or invalid URL)"}

            # Playlist handling
            if info.get("_type") == "playlist":
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

                if not videos:
                    return {"error": "Playlist is empty or blocked"}

                return {"type": "playlist", "title": info.get("title"), "videos": videos}

            # Single video formats
            formats = []
            seen = set()
            for f in info.get("formats", []):
                if not f:
                    continue
                if f.get("vcodec") == "none":
                    continue
                height = f.get("height")
                if not height:
                    continue
                ext = f.get("ext")
                stream_url = f.get("url")
                if not stream_url:
                    continue
                key = (height, ext)
                if key in seen:
                    continue
                seen.add(key)
                formats.append({
                    "quality": f"{height}p",
                    "ext": ext,
                    "url": stream_url,
                    "filesize": f.get("filesize") or f.get("filesize_approx"),
                })

            if not formats:
                return {"error": "No downloadable formats found (possibly blocked by YouTube)"}

            formats = sorted(formats, key=lambda x: int(x["quality"].replace("p", "")), reverse=True)

            return {"type": "video", "title": info.get("title"), "thumbnail": info.get("thumbnail"), "formats": formats}

        except Exception as e:
            last_err = e
            attempts += 1
            wait = 1.5 ** attempts
            logger.warning("Extraction failed, retrying", extra={"attempt": attempts, "error": str(e)})
            time.sleep(wait)

    return {"error": f"Extraction failed after {max_attempts} attempts: {last_err}"}