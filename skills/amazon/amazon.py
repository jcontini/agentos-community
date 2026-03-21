#!/usr/bin/env python3
"""
Amazon skill — search suggestions, product search, and product details.

Uses Amazon's public completion.amazon.com API for keyword suggestions and
httpx with HTTP/2 for product page parsing. No API keys required.
"""

import html as html_lib
import json
import re
import sys
import time
from typing import Any
from urllib.parse import quote_plus

import httpx

# ═══════════════════════════════════════════════════════════════════════════════
# MARKETPLACE & DEPARTMENT REGISTRIES
# ═══════════════════════════════════════════════════════════════════════════════

MARKETPLACES: dict[str, dict[str, str]] = {
    "US": {"mid": "ATVPDKIKX0DER", "tld": "com"},
    "UK": {"mid": "A1F83G8C2ARO7P", "tld": "co.uk"},
    "DE": {"mid": "A1PA6795UKMFR9", "tld": "de"},
    "FR": {"mid": "A13V1IB3VIYBER", "tld": "fr"},
    "JP": {"mid": "A1VC38T7YXB528", "tld": "co.jp"},
    "CA": {"mid": "A2EUQ1WTGCTBG2", "tld": "ca"},
    "AU": {"mid": "A39IBJ37TRP1C6", "tld": "com.au"},
    "IN": {"mid": "A21TJRUUN4KGV", "tld": "in"},
    "ES": {"mid": "A1RKKUPIHCS9HS", "tld": "es"},
    "IT": {"mid": "APJ6JRA9NG5V4", "tld": "it"},
    "MX": {"mid": "A1AM78C64UM0Y8", "tld": "com.mx"},
    "BR": {"mid": "A2Q3Y263D00KWC", "tld": "com.br"},
    "NL": {"mid": "A1805IZSGTT6HS", "tld": "nl"},
    "SE": {"mid": "A2NODRKZP88ZB9", "tld": "se"},
    "SG": {"mid": "A19VAU5U5O7RUS", "tld": "sg"},
    "AE": {"mid": "A2VIGQ35RCS4UG", "tld": "ae"},
    "SA": {"mid": "A17E79C6D8DWNP", "tld": "sa"},
    "TR": {"mid": "A33AVAJ2PDY3EV", "tld": "com.tr"},
    "BE": {"mid": "AMEN7PMS3EDWL", "tld": "com.be"},
    "EG": {"mid": "ARBP9OOSHTCHU", "tld": "eg"},
}

DEPARTMENTS: dict[str, str] = {
    "all": "aps",
    "electronics": "electronics",
    "books": "stripbooks",
    "sports": "sporting",
    "toys": "toys-and-games",
    "fashion": "fashion",
    "grocery": "grocery",
    "beauty": "beauty",
    "automotive": "automotive",
    "garden": "garden",
    "videogames": "videogames",
    "tools": "tools",
    "baby": "baby-products",
    "office": "office-products",
    "pets": "pets",
    "music": "digital-music",
    "appliances": "appliances",
    "kitchen": "kitchen",
    "movies": "movies-tv",
    "software": "software",
    "health": "hpc",
    "jewelry": "jewelry",
    "watches": "watches",
    "shoes": "shoes",
    "industrial": "industrial",
    "arts": "arts-crafts-sewing",
    "smart-home": "smart-home",
    "kindle": "digital-text",
}

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


def _marketplace(key: str | None) -> dict[str, str]:
    return MARKETPLACES.get((key or "US").upper(), MARKETPLACES["US"])


def _alias(department: str | None) -> str:
    if not department:
        return "aps"
    key = department.lower().strip()
    return DEPARTMENTS.get(key, key)


def _client(**kwargs: Any) -> httpx.Client:
    return httpx.Client(
        http2=True,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
        },
        follow_redirects=True,
        timeout=30.0,
        **kwargs,
    )


def _clean(text: str | None) -> str | None:
    if not text:
        return None
    text = re.sub(r"<[^>]+>", "", text)
    text = html_lib.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _extract(pattern: str, text: str, group: int = 1) -> str | None:
    m = re.search(pattern, text, re.S)
    return m.group(group).strip() if m else None


def _parse_price(price_str: str | None) -> float | None:
    if not price_str:
        return None
    digits = re.sub(r"[^\d.]", "", price_str)
    try:
        return float(digits)
    except ValueError:
        return None


def _parse_rating(rating_str: str | None) -> float | None:
    if not rating_str:
        return None
    m = re.search(r"([\d.]+)\s+out of", rating_str)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


def _parse_count(count_str: str | None) -> int | None:
    if not count_str:
        return None
    count_str = count_str.replace(",", "").strip("() \t\n")
    if count_str.upper().endswith("K"):
        try:
            return int(float(count_str[:-1]) * 1000)
        except ValueError:
            return None
    digits = re.sub(r"[^\d]", "", count_str)
    return int(digits) if digits else None


def _is_captcha(body: str) -> bool:
    markers = ["Robot Check", "Sorry! Something went wrong", "ap_captcha", "opfcaptcha"]
    return any(m in body for m in markers)


# ═══════════════════════════════════════════════════════════════════════════════
# SEARCH SUGGESTIONS — completion.amazon.com public JSON API
# ═══════════════════════════════════════════════════════════════════════════════


def search_suggestions(
    query: str,
    department: str | None = None,
    personalized: bool = False,
    marketplace: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch autocomplete keyword suggestions from Amazon's public completion API.

    Returns up to 10 keyword suggestions. When personalized=True, the API uses
    Amazon's p13n-expert-pd-ops-ranker for population-level personalized ranking
    instead of the default organic strategy.
    """
    mp = _marketplace(marketplace)
    alias = _alias(department)
    tld = mp["tld"]

    params: dict[str, str] = {
        "mid": mp["mid"],
        "alias": alias,
        "prefix": query,
        "suggestion-type": "KEYWORD",
    }

    if personalized:
        params["session-id"] = "000-0000000-0000000"
        params["lop"] = "en_US"
        params["page-type"] = "Gateway"
        params["site-variant"] = "desktop"

    url = f"https://completion.amazon.{tld}/api/2017/suggestions"

    with _client() as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    suggestions = [
        {
            "value": s["value"],
            "search_url": f"https://www.amazon.{tld}/s?k={quote_plus(s['value'])}",
            "strategy": s.get("strategyId", "organic"),
            "ref_tag": s.get("refTag"),
            "department": alias,
            "marketplace": (marketplace or "US").upper(),
        }
        for s in (data.get("suggestions") or [])
        if s.get("value")
    ]
    return {"suggestions": suggestions, "count": len(suggestions)}


# ═══════════════════════════════════════════════════════════════════════════════
# SEARCH PRODUCTS — HTML parsing of search result pages
# ═══════════════════════════════════════════════════════════════════════════════


def search_products(
    query: str,
    department: str | None = None,
    page: int = 1,
    marketplace: str | None = None,
) -> list[dict[str, Any]]:
    """Search Amazon products by parsing search result HTML.

    Navigates to the homepage first to establish a session (anti-bot mitigation),
    then fetches the search results page and extracts product cards.
    """
    mp = _marketplace(marketplace)
    alias = _alias(department)
    tld = mp["tld"]
    base = f"https://www.amazon.{tld}"

    search_params: dict[str, str] = {"k": query}
    if page > 1:
        search_params["page"] = str(page)
    if alias != "aps":
        search_params["i"] = alias

    with _client() as client:
        client.get(base, headers={"Accept": "text/html"})
        time.sleep(0.5)
        resp = client.get(
            f"{base}/s",
            params=search_params,
            headers={"Accept": "text/html,application/xhtml+xml"},
        )
        resp.raise_for_status()
        body = resp.text

    if _is_captcha(body):
        raise RuntimeError(
            "Amazon returned a CAPTCHA or block page. "
            "Try again later, or use search_suggestions which uses the JSON API with no blocking."
        )

    return _parse_search_results(body, tld)


def _parse_search_results(body: str, tld: str) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []

    # data-asin appears before data-component-type in Amazon's HTML
    pattern = re.compile(
        r'data-asin="([A-Z0-9]{10})"[^>]*?'
        r'data-component-type="s-search-result"',
    )

    matches = list(pattern.finditer(body))
    for i, m in enumerate(matches):
        asin = m.group(1)
        start = body.rfind("<div", max(0, m.start() - 300), m.start())
        if start == -1:
            start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else min(start + 6000, len(body))
        block = body[start:end]

        # h2 has aria-label with full title; span inside has the same text
        title_m = re.search(r'<h2[^>]*aria-label="([^"]+)"', block)
        if not title_m:
            title_m = re.search(r"<h2[^>]*>.*?<span[^>]*>(.*?)</span>", block, re.S)
        title = _clean(title_m.group(1)) if title_m else None
        if not title:
            continue

        price_m = re.search(
            r'<span class="a-price"[^>]*>.*?<span class="a-offscreen">(.*?)</span>',
            block, re.S,
        )
        price = price_m.group(1).strip() if price_m else None

        rating_m = re.search(r'<span class="a-icon-alt">(.*?)</span>', block)
        rating = _parse_rating(rating_m.group(1) if rating_m else None)

        count_m = re.search(r'<span[^>]*class="[^"]*s-underline-text[^"]*"[^>]*>(.*?)</span>', block)
        ratings_count = _parse_count(count_m.group(1) if count_m else None)

        img_m = re.search(r'<img[^>]+class="s-image"[^>]+src="([^"]+)"', block)
        image = img_m.group(1) if img_m else None

        prime = 'aria-label="Amazon Prime"' in block or "s-prime" in block
        sponsored = "AdHolder" in block

        products.append({
            "asin": asin,
            "title": title,
            "price": price,
            "price_amount": _parse_price(price),
            "rating": rating,
            "ratings_count": ratings_count,
            "image_url": image,
            "url": f"https://www.amazon.{tld}/dp/{asin}",
            "prime": prime,
            "sponsored": sponsored,
        })

    return products


# ═══════════════════════════════════════════════════════════════════════════════
# GET PRODUCT — HTML + a-state parsing of product detail pages
# ═══════════════════════════════════════════════════════════════════════════════


def get_product(
    asin: str,
    marketplace: str | None = None,
) -> dict[str, Any]:
    """Fetch detailed product info from an Amazon product detail page."""
    mp = _marketplace(marketplace)
    tld = mp["tld"]
    base = f"https://www.amazon.{tld}"

    with _client() as client:
        client.get(base, headers={"Accept": "text/html"})
        time.sleep(0.5)
        resp = client.get(
            f"{base}/dp/{asin}",
            headers={"Accept": "text/html,application/xhtml+xml"},
        )
        resp.raise_for_status()
        body = resp.text

    if _is_captcha(body):
        raise RuntimeError("Amazon returned a CAPTCHA or block page.")

    return _parse_product_page(body, asin, tld)


def _parse_product_page(body: str, asin: str, tld: str) -> dict[str, Any]:
    title = _clean(_extract(r'<span id="productTitle"[^>]*>(.*?)</span>', body))

    price = _extract(
        r'(?:id="corePrice_feature_div"|id="corePriceDisplay_desktop_feature_div").*?'
        r'<span class="a-offscreen">(.*?)</span>',
        body,
    )
    if not price:
        price = _extract(r'<span class="a-offscreen">(\$[\d,.]+)</span>', body)

    rating = _parse_rating(_extract(
        r'id="acrPopover".*?<span class="a-icon-alt">(.*?)</span>', body,
    ))

    ratings_count = _parse_count(_extract(
        r'id="acrCustomerReviewText"[^>]*>(.*?)</span>', body,
    ))

    brand_raw = _clean(_extract(r'<a id="bylineInfo"[^>]*>(.*?)</a>', body))
    brand = brand_raw
    if brand:
        brand = re.sub(r"^Visit the\s+", "", brand, flags=re.I)
        brand = re.sub(r"\s+Store$", "", brand, flags=re.I)
        brand = re.sub(r"^Brand:\s*", "", brand, flags=re.I)

    availability = _clean(_extract(
        r'id="availability".*?<span[^>]*>(.*?)</span>', body,
    ))

    main_image = _extract(r'id="landingImage"[^>]+src="([^"]+)"', body)

    description = _clean(_extract(
        r'id="productDescription"[^>]*>(.*?)</div>', body,
    ))
    if not description:
        description = _clean(_extract(
            r'id="feature-bullets"[^>]*>(.*?)</div>', body,
        ))

    # Breadcrumb categories
    crumb_section = body[:body.find('id="productTitle"')] if 'id="productTitle"' in body else body[:8000]
    cats_raw = re.findall(
        r'id="wayfinding-breadcrumbs_feature_div".*?</ul>',
        crumb_section, re.S,
    )
    categories: list[str] = []
    if cats_raw:
        categories = [c for c in (_clean(c) for c in re.findall(r"<a[^>]*>(.*?)</a>", cats_raw[0], re.S)) if c]

    # Images from ImageBlockATF — extract the JSON array after 'initial':
    images: list[str] = []
    img_start = body.find("'colorImages': { 'initial': [")
    if img_start >= 0:
        arr_start = body.index("[", img_start)
        depth = 0
        arr_end = arr_start
        for ci, ch in enumerate(body[arr_start:arr_start + 20000], arr_start):
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    arr_end = ci + 1
                    break
        try:
            img_data = json.loads(body[arr_start:arr_end])
            images = [
                item.get("hiRes") or item.get("large") or ""
                for item in img_data
                if isinstance(item, dict)
            ]
            images = [u for u in images if u]
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "asin": asin,
        "title": title,
        "description": description,
        "price": price,
        "price_amount": _parse_price(price),
        "brand": brand,
        "rating": rating,
        "ratings_count": ratings_count,
        "review_count": ratings_count,
        "image_url": main_image or (images[0] if images else None),
        "images": images[:10],
        "url": f"https://www.amazon.{tld}/dp/{asin}",
        "availability": availability,
        "categories": categories,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ORDER HISTORY — authenticated HTML scraping
# ═══════════════════════════════════════════════════════════════════════════════


def _cookie(ctx: dict[str, Any]) -> str | None:
    """Extract cookie header from the runtime params context."""
    c = (ctx.get("auth") or {}).get("cookies") or ""
    return c if c else None


def _require_cookies(params: dict[str, Any] | None, op: str) -> str:
    cookie_header = params and _cookie(params)
    if not cookie_header:
        raise ValueError(
            f"{op} requires Amazon session cookies. "
            "Sign in at amazon.com; AgentOS provides cookies via the web connection."
        )
    return cookie_header


def _auth_client(cookie_header: str) -> httpx.Client:
    return httpx.Client(
        http2=True,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cookie": cookie_header,
        },
        follow_redirects=True,
        timeout=30.0,
    )


def list_orders(params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """List Amazon orders from the order history page."""
    params = params or {}
    cookie_header = _require_cookies(params, "list_orders")
    order_filter = (params.get("params") or {}).get("filter") or "last30"
    page = int((params.get("params") or {}).get("page") or 1)

    base = "https://www.amazon.com"
    url_params: dict[str, str] = {"orderFilter": order_filter}
    if page > 1:
        url_params["startIndex"] = str((page - 1) * 10)

    with _auth_client(cookie_header) as client:
        resp = client.get(f"{base}/gp/your-account/order-history", params=url_params)
        resp.raise_for_status()
        body = resp.text

    if "ap_email" in body or "signIn" in body[:3000]:
        raise RuntimeError(
            "Amazon redirected to login — session cookies are expired or invalid. "
            "Sign in at amazon.com again."
        )

    return _parse_order_history(body)


def _parse_order_history(body: str) -> list[dict[str, Any]]:
    orders: list[dict[str, Any]] = []

    # Each order card is in a .order-card or similar container with an order ID
    order_blocks = re.split(
        r'(?=data-component="orderCard"|id="orderCard_)',
        body,
    )

    for block in order_blocks:
        order_id_m = re.search(r"(\d{3}-\d{7}-\d{7})", block)
        if not order_id_m:
            continue
        order_id = order_id_m.group(1)

        date_m = re.search(
            r"(?:Order placed|Ordered on)\s*(?:</[^>]+>\s*)*([A-Z][a-z]+ \d{1,2}, \d{4})",
            block, re.I,
        )
        order_date = date_m.group(1) if date_m else None

        total_m = re.search(r"(?:Order Total|Grand Total|Total)[^$]*(\$[\d,.]+)", block, re.I)
        total = total_m.group(1) if total_m else None

        status_m = re.search(
            r"(?:Delivered|Arriving|Shipped|Refunded|Cancelled|Returned|Out for delivery)[^<]*",
            block, re.I,
        )
        status = _clean(status_m.group()) if status_m else None

        delivery_m = re.search(
            r"(?:Delivered|Arriving)\s+([A-Z][a-z]+ \d{1,2}(?:,\s*\d{4})?)",
            block, re.I,
        )
        delivery_date = delivery_m.group(1) if delivery_m else None

        # Extract items from the order
        items: list[dict[str, Any]] = []
        for item_m in re.finditer(r'/(?:dp|gp/product)/([A-Z0-9]{10})', block):
            item_asin = item_m.group(1)
            # Look for title near the ASIN link
            link_pos = item_m.start()
            nearby = block[max(0, link_pos - 200):link_pos + 500]
            title_m = re.search(r'aria-label="([^"]+)"', nearby)
            if not title_m:
                title_m = re.search(r'title="([^"]+)"', nearby)
            if not title_m:
                title_m = re.search(r'>([^<]{10,120})</a>', nearby)
            item_title = _clean(title_m.group(1)) if title_m else None

            img_m = re.search(r'<img[^>]+src="(https://m\.media-amazon\.com/images/I/[^"]+)"', nearby)
            item_image = img_m.group(1) if img_m else None

            price_m = re.search(r'\$[\d,.]+', nearby)
            item_price = price_m.group() if price_m else None

            if item_title or item_asin:
                items.append({
                    "asin": item_asin,
                    "title": item_title,
                    "url": f"https://www.amazon.com/dp/{item_asin}",
                    "image_url": item_image,
                    "price": item_price,
                })

        # Deduplicate items by ASIN
        seen_asins: set[str] = set()
        unique_items: list[dict[str, Any]] = []
        for item in items:
            if item["asin"] not in seen_asins:
                seen_asins.add(item["asin"])
                unique_items.append(item)

        orders.append({
            "order_id": order_id,
            "order_date": order_date,
            "total": total,
            "total_amount": _parse_price(total),
            "status": status,
            "delivery_date": delivery_date,
            "item_count": len(unique_items),
            "items": unique_items,
            "url": f"https://www.amazon.com/gp/your-account/order-details?orderID={order_id}",
        })

    return orders


def get_order(params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fetch detailed info for a specific Amazon order."""
    params = params or {}
    cookie_header = _require_cookies(params, "get_order")
    order_id = (params.get("params") or {}).get("order_id", "")
    if not order_id:
        raise ValueError("order_id is required")

    base = "https://www.amazon.com"
    with _auth_client(cookie_header) as client:
        resp = client.get(
            f"{base}/gp/your-account/order-details",
            params={"orderID": order_id},
        )
        resp.raise_for_status()
        body = resp.text

    if "ap_email" in body or "signIn" in body[:3000]:
        raise RuntimeError("Amazon redirected to login — session cookies expired.")

    return _parse_order_detail(body, order_id)


def _parse_order_detail(body: str, order_id: str) -> dict[str, Any]:
    date_m = re.search(
        r"(?:Order placed|Ordered on)\s*(?:</[^>]+>\s*)*([A-Z][a-z]+ \d{1,2}, \d{4})",
        body, re.I,
    )
    order_date = date_m.group(1) if date_m else None

    total_m = re.search(r"(?:Order Total|Grand Total)[^$]*(\$[\d,.]+)", body, re.I)
    total = total_m.group(1) if total_m else None

    status_m = re.search(
        r"(?:Delivered|Arriving|Shipped|Refunded|Cancelled|Returned|Out for delivery)[^<]*",
        body, re.I,
    )
    status = _clean(status_m.group()) if status_m else None

    delivery_m = re.search(
        r"(?:Delivered|Arriving)\s+([A-Z][a-z]+ \d{1,2}(?:,\s*\d{4})?)",
        body, re.I,
    )
    delivery_date = delivery_m.group(1) if delivery_m else None

    # Shipping address
    address_m = re.search(
        r"(?:Shipping Address|Ship to)\s*(?:</[^>]+>\s*)*(.*?)(?=</div|Payment)",
        body, re.I | re.S,
    )
    shipping_address = _clean(address_m.group(1)) if address_m else None

    # Items
    items: list[dict[str, Any]] = []
    seen_asins: set[str] = set()
    for asin_m in re.finditer(r'/(?:dp|gp/product)/([A-Z0-9]{10})', body):
        asin = asin_m.group(1)
        if asin in seen_asins:
            continue
        seen_asins.add(asin)

        pos = asin_m.start()
        nearby = body[max(0, pos - 300):pos + 600]

        title_m = re.search(r'aria-label="([^"]+)"', nearby)
        if not title_m:
            title_m = re.search(r'>([^<]{10,150})</a>', nearby)
        item_title = _clean(title_m.group(1)) if title_m else None

        img_m = re.search(r'<img[^>]+src="(https://m\.media-amazon\.com/images/I/[^"]+)"', nearby)
        item_image = img_m.group(1) if img_m else None

        price_m = re.search(r'\$[\d,.]+', nearby)
        item_price = price_m.group() if price_m else None

        qty_m = re.search(r'[Qq]ty:\s*(\d+)', nearby)
        quantity = int(qty_m.group(1)) if qty_m else 1

        items.append({
            "asin": asin,
            "title": item_title,
            "url": f"https://www.amazon.com/dp/{asin}",
            "image_url": item_image,
            "price": item_price,
            "quantity": quantity,
        })

    return {
        "order_id": order_id,
        "order_date": order_date,
        "total": total,
        "total_amount": _parse_price(total),
        "status": status,
        "delivery_date": delivery_date,
        "shipping_address": shipping_address,
        "item_count": len(items),
        "items": items,
        "url": f"https://www.amazon.com/gp/your-account/order-details?orderID={order_id}",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CLI — for local testing
# ═══════════════════════════════════════════════════════════════════════════════


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(
            "Usage: amazon.py <command> [args...]\n"
            "Commands:\n"
            "  search_suggestions <query> [department] [marketplace]\n"
            "  search_products <query> [department] [marketplace]\n"
            "  get_product <asin> [marketplace]"
        )

    cmd = sys.argv[1]

    if cmd == "search_suggestions":
        query = sys.argv[2] if len(sys.argv) > 2 else "wireless headphones"
        dept = sys.argv[3] if len(sys.argv) > 3 else None
        mkt = sys.argv[4] if len(sys.argv) > 4 else None
        result = search_suggestions(query, department=dept, marketplace=mkt)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == "search_products":
        query = sys.argv[2] if len(sys.argv) > 2 else "usb c cable"
        dept = sys.argv[3] if len(sys.argv) > 3 else None
        mkt = sys.argv[4] if len(sys.argv) > 4 else None
        result = search_products(query, department=dept, marketplace=mkt)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == "get_product":
        asin_val = sys.argv[2] if len(sys.argv) > 2 else "B0BQPNMXQV"
        mkt = sys.argv[4] if len(sys.argv) > 4 else None
        result = get_product(asin_val, marketplace=mkt)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    else:
        raise SystemExit(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
