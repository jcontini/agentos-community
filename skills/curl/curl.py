"""Curl skill — simple URL fetching via HTTP GET."""

from lxml import html
from agentos import http, provides, returns, timeout, web_read


@returns("webpage")
@provides(web_read)
@timeout(35)
def read_webpage(*, url: str, **params) -> dict:
    """Fetch a URL and return its content, title, and content type.

    Args:
        url: URL to fetch
    """
    resp = http.get(url, timeout=30.0)

    content = resp["body"]
    content_type = resp["headers"].get("content-type", "text/plain")
    content_type = content_type.split(";")[0].strip()

    title = ""
    if content_type.startswith("text/html") and content:
        doc = html.fromstring(content[:4000])
        title_el = doc.cssselect("title")
        if title_el:
            title = title_el[0].text_content().strip()

    return {
        "id": url,
        "name": title or url,
        "url": url,
        "content": content,
        "contentType": content_type,
    }
