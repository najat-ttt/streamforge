import yt_dlp


def analyze_video(url):
    try:
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "nocheckcertificate": True,
            "geo_bypass": True,

            # 🔥 VERY IMPORTANT (fix bot detection)
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept-Language": "en-US,en;q=0.9",
            },
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # =========================
        # PLAYLIST
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
            # skip invalid
            if f.get("vcodec") == "none":
                continue

            height = f.get("height")
            if not height:
                continue

            ext = f.get("ext")

            key = (height, ext)
            if key in seen:
                continue
            seen.add(key)

            formats.append({
                "quality": f"{height}p",
                "ext": ext,
                "url": f.get("url"),
                "acodec": f.get("acodec"),
                "vcodec": f.get("vcodec"),
                "filesize": f.get("filesize") or f.get("filesize_approx"),
            })

        # 🔥 sort highest → lowest
        formats = sorted(
            formats,
            key=lambda x: int(x["quality"].replace("p", "")),
            reverse=True
        )

        return {
            "type": "video",
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "formats": formats
        }

    except Exception as e:
        return {
            "error": str(e)
        }