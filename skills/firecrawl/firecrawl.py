"""Firecrawl — browser-rendered web scraping via API."""

from agentos import http

API_BASE = "https://api.firecrawl.dev/v1"


def read_webpage(*, url: str, wait_for_js: int = 0, timeout: int = 30000, **params) -> dict:
    """Read a URL with browser rendering (handles JS-heavy sites)."""
    api_key = params.get("auth", {}).get("key", "")
    resp = http.post(
        f"{API_BASE}/scrape",
        json={
            "url": url,
            "formats": ["markdown"],
            "onlyMainContent": True,
            "waitFor": wait_for_js,
            "timeout": timeout,
        },
        headers={"Authorization": f"Bearer {api_key}"},
        profile="api",
    )
    data = (resp["json"] or {}).get("data") or {}
    meta = data.get("metadata") or {}
    return {
        "id": meta.get("sourceURL") or meta.get("url") or url,
        "name": meta.get("title") or meta.get("ogTitle"),
        "text": data.get("markdown") or meta.get("description"),
        "url": meta.get("sourceURL") or meta.get("url") or url,
        "image": meta.get("ogImage") or meta.get("image") or meta.get("og:image"),
        "author": meta.get("author") or meta.get("article:author"),
        "datePublished": (
            meta.get("publishedTime")
            or meta.get("publishedDate")
            or meta.get("article:published_time")
        ),
        "content_type": "text/markdown",
    }
