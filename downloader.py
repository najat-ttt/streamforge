import yt_dlp


def analyze_video(url):
    try:
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

        # SINGLE VIDEO
        formats = []
        seen = set()

        for f in info.get("formats", []):
            if f.get("vcodec") == "none":
                continue

            height = f.get("height")
            if not height:
                continue

            key = (height, f.get("ext"))
            if key in seen:
                continue
            seen.add(key)

            formats.append({
                "quality": f"{height}p",
                "ext": f.get("ext"),
                "url": f.get("url")
            })

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
        return {"error": str(e)}