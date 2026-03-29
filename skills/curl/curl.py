"""Curl skill — simple URL fetching via HTTP GET."""

from bs4 import BeautifulSoup
from agentos import http


def read_webpage(*, url: str, **params) -> dict:
    """Fetch a URL and return its content, title, and content type."""
    resp = http.get(url, timeout=30.0)

    content = resp["body"]
    content_type = resp["headers"].get("content-type", "text/plain")
    content_type = content_type.split(";")[0].strip()

    title = ""
    if content_type.startswith("text/html"):
        soup = BeautifulSoup(content[:4000], "html.parser")
        if soup.title:
            title = soup.title.get_text(strip=True)

    return {
        "url": url,
        "title": title,
        "content": content,
        "content_type": content_type,
    }
