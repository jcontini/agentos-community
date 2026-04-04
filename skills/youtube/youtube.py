"""YouTube — video metadata and transcripts via yt-dlp Python API.

yt-dlp is installed as a Homebrew formula with its own Python venv.
We add its site-packages to sys.path so we can use the Python API
directly (no subprocess, no temp files, no jq).
"""

import glob
import sys
import urllib.request
import json

# Add yt-dlp's own site-packages to path (stable symlink, version-agnostic)
_ytdlp_paths = glob.glob("/opt/homebrew/opt/yt-dlp/libexec/lib/python*/site-packages")
for _p in _ytdlp_paths:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    import yt_dlp
except ImportError as e:
    raise ImportError(
        "yt-dlp is required: brew install yt-dlp"
    ) from e

SITE = "https://www.youtube.com"

_BASE_OPTS = {
    "quiet": True,
    "noWarnings": True,
    "socketTimeout": 30,
}


def _upload_date_to_iso(d: str | None) -> str | None:
    """Convert yt-dlp's YYYYMMDD string to ISO 8601 date."""
    if not d or len(d) != 8:
        return d
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}"


def _map_flat_entry(e: dict) -> dict:
    """Map a flat playlist entry (from extract_flat) to shape-native video fields."""
    vid_id = e.get("id", "")
    channel_id = e.get("channel_id", "")
    channel = e.get("channel") or e.get("uploader")

    thumbnails = e.get("thumbnails") or []
    thumbnail = thumbnails[-1]["url"] if thumbnails else e.get("thumbnail")

    playlist = e.get("playlist") if (e.get("playlist_id") or "").startswith("PL") else None
    playlist_id = e.get("playlist_id") if playlist else None

    result = {
        "id": vid_id,
        "name": e.get("title"),
        "content": e.get("description"),
        "url": f"{SITE}/watch?v={vid_id}" if vid_id else e.get("webpage_url"),
        "image": thumbnail,
        "durationMs": int(e["duration"] * 1000) if e.get("duration") else None,
        "viewCount": e.get("view_count"),
    }
    if channel_id:
        result["channel"] = {
            "id": channel_id,
            "name": channel,
            "url": e.get("channel_url"),
        }
    if playlist_id:
        result["add_to"] = {
            "id": playlist_id,
            "name": playlist,
            "url": f"{SITE}/playlist?list={playlist_id}",
        }
    return result


def _map_full_info(info: dict) -> dict:
    """Map a full yt-dlp info dict to shape-native video fields."""
    vid_id = info.get("id", "")
    channel_id = info.get("channel_id", "")
    channel = info.get("channel") or info.get("uploader")
    author = channel  # video author = channel name

    result = {
        "id": vid_id,
        "name": info.get("title"),
        "content": info.get("description"),
        "url": info.get("webpage_url") or f"{SITE}/watch?v={vid_id}",
        "image": info.get("thumbnail"),
        "author": author,
        "published": _upload_date_to_iso(info.get("upload_date")),
        "durationMs": int(info["duration"] * 1000) if info.get("duration") else None,
        "resolution": info.get("resolution"),
        "viewCount": info.get("view_count"),
        "likeCount": info.get("like_count"),
        "commentCount": info.get("comment_count"),
    }
    if channel_id:
        result["channel"] = {
            "id": channel_id,
            "name": channel,
            "url": info.get("channel_url"),
        }
    return result


def _ydl(extra: dict | None = None) -> yt_dlp.YoutubeDL:
    opts = dict(_BASE_OPTS)
    if extra:
        opts.update(extra)
    return yt_dlp.YoutubeDL(opts)


# ─────────────────────────────────────────────────────────────────────────────
# Operations
# ─────────────────────────────────────────────────────────────────────────────

def search_videos(query: str, limit: int = 50) -> list[dict]:
    with _ydl({"extractFlat": "in_playlist"}) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
    return [_map_flat_entry(e) for e in (info.get("entries") or [])]


def search_recent_video(query: str, limit: int = 50) -> list[dict]:
    with _ydl({"extractFlat": "in_playlist"}) as ydl:
        info = ydl.extract_info(f"ytsearchdate{limit}:{query}", download=False)
    return [_map_flat_entry(e) for e in (info.get("entries") or [])]


def list_videos(url: str, limit: int = 50) -> list[dict]:
    with _ydl({"extractFlat": "in_playlist", "playlistend": limit}) as ydl:
        info = ydl.extract_info(url, download=False)
    return [_map_flat_entry(e) for e in (info.get("entries") or [])]


def get_video(url: str) -> dict:
    with _ydl() as ydl:
        info = ydl.extract_info(url, download=False)
    return _map_full_info(info)


def transcript_video(url: str, lang: str = "en", format: str = "text") -> dict:
    """Fetch video metadata + transcript. No temp files — captions fetched in memory."""
    with _ydl() as ydl:
        info = ydl.extract_info(url, download=False)

    vid = _map_full_info(info)

    # Try automatic captions first, then manual subtitles
    captions = (
        info.get("automatic_captions", {}).get(lang)
        or info.get("subtitles", {}).get(lang)
    )
    if not captions:
        # Fallback: try first available language
        captions = next(iter(info.get("automatic_captions", {}).values()), None)

    if not captions:
        vid["error"] = f"No captions available in language: {lang}"
        return vid

    # Find json3 format for structured parsing; fallback to any format
    cap_entry = next((c for c in captions if c.get("ext") == "json3"), captions[0])
    source_type = "auto_caption" if cap_entry in captions else "manual"

    with urllib.request.urlopen(cap_entry["url"], timeout=30) as r:
        cap_data = json.loads(r.read())

    events = [
        e for e in cap_data.get("events", [])
        if e.get("segs") and any(s.get("utf8", "").strip() for s in e["segs"])
    ]

    if format == "segments":
        segments = [
            {
                "startMs": e.get("tStartMs", 0),
                "endMs": e.get("tStartMs", 0) + e.get("dDurationMs", 0),
                "content": "".join(s.get("utf8", "") for s in e["segs"]).replace("\n", " ").strip(),
            }
            for e in events
            if "".join(s.get("utf8", "") for s in e["segs"]).strip()
        ]
        transcript = " ".join(s["content"] for s in segments)
        vid.update({
            "content": transcript,
            "transcriptSegments": segments,
            "segmentCount": len(segments),
            "sourceType": source_type,
            "language": lang,
        })
    else:
        transcript = " ".join(
            "".join(s.get("utf8", "") for s in e["segs"]).replace("\n", " ").strip()
            for e in events
        ).strip()
        vid.update({
            "content": transcript,
            "sourceType": source_type,
            "language": lang,
        })

    return vid


def get_channel(url: str) -> dict:
    with _ydl({"extractFlat": True, "playlistend": 0}) as ydl:
        info = ydl.extract_info(url, download=False)

    thumbnails = info.get("thumbnails") or []
    # Avatar = square thumbnail; banner = wide one
    avatar = next(
        (t["url"] for t in sorted(thumbnails, key=lambda t: -(t.get("width") or 0))
         if t.get("width") and t.get("height") and t["width"] == t["height"]),
        None,
    )
    banner = next(
        (t["url"] for t in thumbnails if t.get("id") == "banner_uncropped"),
        None,
    )
    return {
        "id": info.get("channel_id") or info.get("id"),
        "name": info.get("channel") or info.get("uploader") or info.get("title"),
        "content": info.get("description"),
        "url": info.get("channel_url") or url,
        "image": avatar,
        "banner": banner,
        "subscriberCount": info.get("channel_follower_count"),
    }


def get_avatar_channel(url: str) -> dict:
    """Quick fetch of channel avatar via og:image — ~1s."""
    from agentos import http
    resp = http.get(url, timeout=10)
    html = resp["body"]

    import re
    m = re.search(r'og:image["\s]+content="([^"]+)"', html)
    avatar = m.group(1) if m else None
    return {"url": url, "image": avatar}


def list_posts(url: str, limit: int = 50) -> list[dict]:
    """List comments on a video as post entities."""
    opts = {
        "getcomments": True,
        "extractorArgs": {"youtube": {"maxComments": [str(limit), "all", "all", "100"]}},
    }
    with _ydl(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    vid_id = info.get("id", "")
    # Root post entity for the video itself (comments reply to this)
    video_post_id = f"{vid_id}_post"

    posts = []
    for c in (info.get("comments") or []):
        author_id = c.get("author_id", "")
        parent = c.get("parent", "root")
        post = {
            "id": c.get("id"),
            "content": c.get("text"),
            "url": f"{SITE}/watch?v={vid_id}&lc={c.get('id')}",
            "published": _upload_date_to_iso(
                str(c.get("timestamp", ""))[:8] if c.get("timestamp") else None
            ),
            "likes": c.get("like_count"),
            "postedBy": {
                "id": author_id,
                "name": c.get("author"),
                "url": c.get("author_url"),
                "image": c.get("author_thumbnail"),
            } if author_id else None,
            "repliesTo": {
                "id": video_post_id if parent == "root" else parent,
            },
        }
        posts.append(post)
    return posts
