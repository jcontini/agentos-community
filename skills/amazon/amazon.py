#!/usr/bin/env python3
"""Amazon retail search for AgentOS.

Public search hits www.amazon.com/s without login. Optional `web` connection
adds browser cookies for the same endpoint (personalized layout/pricing).

Amazon has no general-purpose public product JSON API for consumers; the
Product Advertising API requires AWS + Associate account signing. This module
scrapes organic SERP HTML with httpx + HTTP/2 (see CONTRIBUTING.md).
"""

from __future__ import annotations

import html as html_lib
import re
from urllib.parse import quote_plus, urljoin, urlparse

import httpx

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

LISTITEM_RE = re.compile(
    r'<div[^>]*role="listitem"[^>]*data-asin="(B[A-Z0-9]{9})"[^>]*data-component-type="s-search-result"[^>]*>',
    re.I,
)


def _connection_mode(con: object | None) -> str:
    if not isinstance(con, dict):
        return "public"
    name = con.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip().lower()
    return "public"


def _base_url(con: object | None) -> str:
    if isinstance(con, dict) and con.get("base_url"):
        return str(con["base_url"]).rstrip("/")
    return "https://www.amazon.com"


def _client(cookie_header: str) -> httpx.Client:
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Upgrade-Insecure-Requests": "1",
    }
    if cookie_header:
        headers["Cookie"] = cookie_header
    return httpx.Client(http2=True, follow_redirects=True, timeout=30, headers=headers)


def _clean_title(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def _parse_results(html: str, base: str, limit: int) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []

    for m in LISTITEM_RE.finditer(html):
        tag = m.group(0)
        if "AdHolder" in tag:
            continue
        asin = m.group(1)
        if asin in seen:
            continue

        chunk = html[m.end() : m.end() + 28000]

        title = ""
        t_m = re.search(r'<h2[^>]*aria-label="([^"]+)"', chunk)
        if t_m:
            title = html_lib.unescape(t_m.group(1).strip())
        if not title:
            t_m = re.search(
                r"<h2[^>]*>\s*<span[^>]*>(.*?)</span>\s*</h2>", chunk, re.S
            )
            if t_m:
                title = html_lib.unescape(_clean_title(t_m.group(1)))
        if not title:
            t_m = re.search(
                r'<span[^>]*class="[^"]*a-text-normal[^"]*"[^>]*>(.*?)</span>',
                chunk,
                re.S,
            )
            if t_m:
                title = html_lib.unescape(_clean_title(t_m.group(1)))
        if not title or len(title) < 3:
            continue

        path_m = re.search(rf'href="(/[^"#]*/dp/{re.escape(asin)}[^"]*)"', chunk)
        if path_m:
            path = path_m.group(1).split("?")[0]
            url = urljoin(base + "/", path.lstrip("/"))
        else:
            url = f"{base}/dp/{asin}"

        img_m = re.search(r"https://m\.media-amazon\.com/images/I/[^\"\s?]+", chunk)
        image = img_m.group(0) if img_m else None

        pw = re.search(r'class="a-price-whole"[^>]*>([0-9.,]+)', chunk)
        frac = re.search(r'class="a-price-fraction"[^>]*>([0-9]+)', chunk)
        price = ""
        if pw:
            price = pw.group(1).rstrip(".")
            if frac:
                price = f"{price}.{frac.group(1)}"

        rating_m = re.search(
            r'aria-label="([0-9]+(?:\.[0-9]+)?)\s+out of\s+5\s+stars"', chunk
        )
        reviews_m = re.search(r'aria-label="([0-9,]+)\s+ratings?"', chunk)
        bits = []
        if price:
            bits.append(f"${price}" if price[0].isdigit() else price)
        if rating_m:
            bits.append(f"{rating_m.group(1)}★")
        if reviews_m:
            bits.append(f"{reviews_m.group(1)} ratings")
        text = " · ".join(bits) if bits else ""

        seen.add(asin)
        out.append(
            {
                "asin": asin,
                "title": title,
                "url": url,
                "image": image,
                "price": price or None,
                "rating": float(rating_m.group(1)) if rating_m else None,
                "text": text,
            }
        )
        if len(out) >= limit:
            break

    return out


def search_products(
    query: str,
    limit: int = 10,
    url: str | None = None,
    cookie_header: str = "",
    connection: dict | None = None,
) -> list[dict]:
    """Search Amazon product grid; returns raw dicts for the `product` adapter."""
    base = _base_url(connection)
    mode = _connection_mode(connection)

    with _client(cookie_header) as client:
        if url and str(url).strip():
            raw_url = str(url).strip()
            host = (urlparse(raw_url).netloc or "").lower()
            if "amazon." not in host:
                raise ValueError("url must be an Amazon retail host (e.g. www.amazon.com)")
            fetch_url = raw_url
        else:
            q = (query or "").strip()
            if not q:
                raise ValueError("query is required unless url is set")
            fetch_url = f"{base}/s?k={quote_plus(q)}"

        r = client.get(fetch_url)
        r.raise_for_status()
        html = r.text

    return _parse_results(html, base, max(1, min(int(limit or 10), 24)))


def op_search(
    query: str = "",
    limit: int = 10,
    url: str | None = None,
    cookie_header: str = "",
    connection: dict | None = None,
) -> list[dict]:
    """AgentOS python: entry — `cookie_header` from jaq `.auth.cookies // ""`."""
    return search_products(
        query=query, limit=limit, url=url, cookie_header=cookie_header, connection=connection
    )
