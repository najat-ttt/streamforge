import yt_dlp


def analyze_video(url):
    try:
        # =========================
        # CORE CONFIG (ANTI-BLOCK)
        # =========================
        ydl_opts = {
            "quiet": True,
            "skip_download": True,

            # 🔐 VERY IMPORTANT (fix bot detection)
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },

            "cookiefile": "cookies.txt",

            # Better extraction
            "nocheckcertificate": True,
            "ignoreerrors": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # =========================
        # PLAYLIST HANDLING
        # =========================
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

            return {
                "type": "playlist",
                "title": info.get("title"),
                "videos": videos
            }

        # =========================
        # SINGLE VIDEO
        # =========================
        formats = []
        seen = set()

        for f in info.get("formats", []):
            # Skip audio-only
            if f.get("vcodec") == "none":
                continue

            height = f.get("height")
            if not height:
                continue

            ext = f.get("ext")

            # Avoid duplicates (same resolution + ext)
            key = (height, ext)
            if key in seen:
                continue
            seen.add(key)

            formats.append({
                "quality": f"{height}p",
                "ext": ext,
                "url": f.get("url"),  # direct stream URL
                "filesize": f.get("filesize") or f.get("filesize_approx"),
            })

        # Sort best → worst
        formats = sorted(
            formats,
            key=lambda x: int(x["quality"].replace("p", "")),
            reverse=True
        )

        return {
            "type": "video",
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "formats": formats
        }

    except Exception as e:
        return {
            "error": str(e)
        }