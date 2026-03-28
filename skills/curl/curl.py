"""Curl skill — simple URL fetching via HTTP GET."""

import re

from agentos import surf


def read_webpage(*, url: str, **params) -> dict:
    """Fetch a URL and return its content, title, and content type."""
    with surf(timeout=30.0) as client:
        resp = client.get(url)
        resp.raise_for_status()

    content = resp.text
    content_type = resp.headers.get("content-type", "text/plain")
    # Strip charset suffix: "text/html; charset=utf-8" -> "text/html"
    content_type = content_type.split(";")[0].strip()

    title = ""
    if content_type.startswith("text/html"):
        m = re.search(r"<title[^>]*>([^<]+)</title>", content, re.IGNORECASE)
        if m:
            title = m.group(1).strip()

    return {
        "url": url,
        "title": title,
        "content": content,
        "content_type": content_type,
    }
