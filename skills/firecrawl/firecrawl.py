"""Firecrawl — browser-rendered web scraping via API."""

from agentos import http, connection, provides, returns, web_read

API_BASE = "https://api.firecrawl.dev/v1"


@returns("webpage")
@provides(web_read)
@connection("api")
async def read_webpage(*, url: str, wait_for_js: int = 0, timeout: int = 30000, **params) -> dict:
    """Read a URL with browser rendering (handles JS-heavy sites)."""
    api_key = params.get("auth", {}).get("key", "")
    resp = await http.post(
        f"{API_BASE}/scrape",
        json={
            "url": url,
            "formats": ["markdown"],
            "onlyMainContent": True,
            "waitFor": wait_for_js,
            "timeout": timeout,
        },
        **http.headers(accept="json", extra={"Authorization": f"Bearer {api_key}"}),
    )
    data = (resp["json"] or {}).get("data") or {}
    meta = data.get("metadata") or {}
    return {
        "id": meta.get("sourceURL") or meta.get("url") or url,
        "name": meta.get("title") or meta.get("ogTitle"),
        "content": data.get("markdown") or meta.get("description"),
        "url": meta.get("sourceURL") or meta.get("url") or url,
        "image": meta.get("ogImage") or meta.get("image") or meta.get("og:image"),
        "author": meta.get("author") or meta.get("article:author"),
        "published": (
            meta.get("publishedTime")
            or meta.get("publishedDate")
            or meta.get("article:published_time")
        ),
        "contentType": "text/markdown",
    }
