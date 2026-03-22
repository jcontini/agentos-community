#!/usr/bin/env python3
"""
Amazon skill — search, products, order history, and account identity.

Uses Amazon's public completion.amazon.com API for keyword suggestions and
httpx with HTTP/2 for HTML page parsing. Order history and account operations
use session cookies from a browser cookie provider. No API keys required.
"""

import html as html_lib
import json
import re
import sys
import time
from typing import Any
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup, Tag

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
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
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
# ORDER HISTORY — authenticated HTML scraping with BeautifulSoup
# ═══════════════════════════════════════════════════════════════════════════════

BASE = "https://www.amazon.com"

AUTH_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Cache-Control": "max-age=0",
    "Device-Memory": "8",
    "Downlink": "10",
    "Dpr": "2",
    "Ect": "4g",
    "Rtt": "50",
    "Sec-Ch-Device-Memory": "8",
    "Sec-Ch-Dpr": "2",
    "Sec-Ch-Ua": '"Chromium";v="145", "Not:A-Brand";v="99"',
    "Sec-Ch-Ua-Full-Version-List": '"Chromium";v="145.0.7632.6", "Not:A-Brand";v="99.0.0.0"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Ch-Viewport-Width": "1512",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Viewport-Width": "1512",
}


def _cookie(ctx: dict[str, Any]) -> str | None:
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


def _parse_cookie_header(cookie_header: str) -> dict[str, str]:
    """Parse a raw Cookie header string into a dict for httpx's cookie jar."""
    cookies: dict[str, str] = {}
    for pair in cookie_header.split(";"):
        pair = pair.strip()
        if "=" in pair:
            k, v = pair.split("=", 1)
            cookies[k.strip()] = v.strip()
    return cookies


SKIP_COOKIES = {"csd-key", "csm-hit", "aws-waf-token"}


def _auth_client(cookie_header: str) -> httpx.Client:
    headers = dict(AUTH_HEADERS)
    headers["Host"] = "www.amazon.com"
    cookies = {
        k: v for k, v in _parse_cookie_header(cookie_header).items()
        if k not in SKIP_COOKIES
    }
    return httpx.Client(
        http2=True,
        headers=headers,
        cookies=cookies,
        follow_redirects=True,
        timeout=30.0,
    )


def _warm_session(client: httpx.Client) -> None:
    """Visit homepage first to provision session cookies and avoid bot detection on sensitive pages."""
    client.get(BASE, headers={"Sec-Fetch-Site": "none"})
    time.sleep(1.0)


def _is_login_redirect(resp: httpx.Response, body: str) -> bool:
    if "ap/signin" in str(resp.url):
        return True
    if "form[name='signIn']" in body[:5000]:
        return True
    return "ap_email" in body[:3000] or "signIn" in body[:3000]


def _soup(body: str) -> BeautifulSoup:
    return BeautifulSoup(body, "html.parser")


def _select(tag: Tag | BeautifulSoup, selectors: list[str]) -> list[Tag]:
    for sel in selectors:
        result = tag.select(sel)
        if result:
            return result
    return []


def _select_one(tag: Tag | BeautifulSoup, selectors: list[str]) -> Tag | None:
    for sel in selectors:
        result = tag.select_one(sel)
        if result:
            return result
    return None


def _text(tag: Tag | None) -> str | None:
    if tag is None:
        return None
    t = tag.get_text(strip=True)
    return t if t else None


# ─── CSS selectors (derived from amazon-orders library) ──────────────────────

ORDER_CARD_SEL = ["div.order-card", "div.order"]
ORDER_ID_SEL = [
    "[data-component='orderId']",
    ".order-date-invoice-item :is(bdi, span)[dir='ltr']",
    ".yohtmlc-order-id :is(bdi, span)[dir='ltr']",
    ":is(bdi, span)[dir='ltr']",
]
ORDER_DATE_SEL = [
    "[data-component='orderDate']",
    "span.order-date-invoice-item",
    "[data-component='briefOrderInfo'] div.a-column",
]
ORDER_TOTAL_SEL = [
    "div.yohtmlc-order-total span.value",
    "div.order-header div.a-column.a-span2",
    "div.order-header div.a-col-left .a-span9",
]
ITEM_SEL = [
    "[data-component='purchasedItems'] .a-fixed-left-grid",
    "div:has(> div.yohtmlc-item)",
    ".item-box",
]
ITEM_TITLE_SEL = [
    "[data-component='itemTitle']",
    ".yohtmlc-item a",
    ".yohtmlc-product-title",
]
ITEM_LINK_SEL = [
    "[data-component='itemTitle'] a",
    ".yohtmlc-item a",
    ".yohtmlc-product-title a",
]
ITEM_IMG_SEL = ["a img"]
ITEM_PRICE_SEL = [
    "[data-component='unitPrice'] .a-text-price :not(.a-offscreen)",
    ".yohtmlc-item .a-color-price",
]
SHIPMENT_STATUS_SEL = [
    "span.delivery-box__primary-text",
    ".yohtmlc-shipment-status-primaryText",
]


def list_orders(params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """List Amazon orders from the order history page."""
    params = params or {}
    cookie_header = _require_cookies(params, "list_orders")
    order_filter = (params.get("params") or {}).get("filter") or "last30"
    page = int((params.get("params") or {}).get("page") or 1)

    url_params: dict[str, str] = {"timeFilter": order_filter}
    if page > 1:
        url_params["startIndex"] = str((page - 1) * 10)

    with _auth_client(cookie_header) as client:
        _warm_session(client)

        resp = client.get(
            f"{BASE}/your-orders/orders",
            params=url_params,
            headers={"Referer": f"{BASE}/gp/homepage.html"},
        )
        resp.raise_for_status()
        body = resp.text

    if _is_login_redirect(resp, body):
        raise RuntimeError(
            "Amazon redirected to login — session cookies are expired or invalid. "
            "Sign in at amazon.com again."
        )

    return _parse_order_history(body)


def _parse_order_history(body: str) -> list[dict[str, Any]]:
    soup = _soup(body)
    orders: list[dict[str, Any]] = []

    order_cards = _select(soup, ORDER_CARD_SEL)

    for card in order_cards:
        order_id_tag = _select_one(card, ORDER_ID_SEL)
        order_id = _text(order_id_tag)
        if order_id:
            order_id = order_id.strip().lstrip("#").strip()
        if not order_id or not re.match(r"\d{3}-\d{7}-\d{7}", order_id):
            continue

        order_date = None
        total = None
        for li in card.select("li.order-header__header-list-item"):
            li_text = _text(li) or ""
            if "Order placed" in li_text:
                order_date = re.sub(r"^.*?Order [Pp]laced\s*", "", li_text).strip()
            elif li_text.lstrip().startswith("Total"):
                m = re.search(r"\$[\d,.]+", li_text)
                total = m.group() if m else None

        if not order_date:
            date_tag = _select_one(card, ORDER_DATE_SEL)
            order_date = _text(date_tag)
            if order_date:
                order_date = re.sub(r"^.*?Order [Pp]laced\s*", "", order_date).strip()
                order_date = re.sub(r"\s*Order #.*$", "", order_date).strip()

        if not total:
            total_tag = _select_one(card, ORDER_TOTAL_SEL)
            total_text = _text(total_tag)
            if total_text:
                m = re.search(r"\$[\d,.]+", total_text)
                total = m.group() if m else total_text.strip()

        status = None
        status_tag = _select_one(card, SHIPMENT_STATUS_SEL)
        if status_tag:
            status = _clean(_text(status_tag))

        delivery_date = None
        if status:
            dm = re.search(
                r"(?:Delivered|Arriving)\s+([A-Z][a-z]+ \d{1,2}(?:,\s*\d{4})?)",
                status, re.I,
            )
            delivery_date = dm.group(1) if dm else None

        items = _parse_order_items(card)

        orders.append({
            "order_id": order_id,
            "order_date": order_date,
            "total": total,
            "total_amount": _parse_price(total),
            "status": status,
            "delivery_date": delivery_date,
            "item_count": len(items),
            "items": items,
            "url": f"{BASE}/gp/your-account/order-details?orderID={order_id}",
        })

    return orders


def _parse_order_items(card: Tag) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen_asins: set[str] = set()

    item_tags = _select(card, ITEM_SEL)
    for item_tag in item_tags:
        link_tag = _select_one(item_tag, ITEM_LINK_SEL)
        href = link_tag.get("href", "") if link_tag else ""
        asin_m = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", str(href))
        asin = asin_m.group(1) if asin_m else None

        if not asin or asin in seen_asins:
            continue
        seen_asins.add(asin)

        title_tag = _select_one(item_tag, ITEM_TITLE_SEL)
        title = _clean(_text(title_tag))

        img_tag = _select_one(item_tag, ITEM_IMG_SEL)
        image_url = img_tag.get("src") if img_tag else None

        price_tag = _select_one(item_tag, ITEM_PRICE_SEL)
        price = _text(price_tag)

        items.append({
            "asin": asin,
            "title": title,
            "url": f"{BASE}/dp/{asin}",
            "image_url": str(image_url) if image_url else None,
            "price": price,
        })

    if not items:
        for asin_m in re.finditer(r'/(?:dp|gp/product)/([A-Z0-9]{10})', str(card)):
            asin = asin_m.group(1)
            if asin in seen_asins:
                continue
            seen_asins.add(asin)
            items.append({
                "asin": asin,
                "title": None,
                "url": f"{BASE}/dp/{asin}",
                "image_url": None,
                "price": None,
            })

    return items


def get_order(params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fetch detailed info for a specific Amazon order."""
    params = params or {}
    cookie_header = _require_cookies(params, "get_order")
    order_id = (params.get("params") or {}).get("order_id", "")
    if not order_id:
        raise ValueError("order_id is required")

    with _auth_client(cookie_header) as client:
        _warm_session(client)

        resp = client.get(
            f"{BASE}/gp/your-account/order-details",
            params={"orderID": order_id},
            headers={"Referer": f"{BASE}/your-orders/orders"},
        )
        resp.raise_for_status()
        body = resp.text

    if _is_login_redirect(resp, body):
        raise RuntimeError("Amazon redirected to login — session cookies expired.")

    return _parse_order_detail(body, order_id)


def _parse_order_detail(body: str, order_id: str) -> dict[str, Any]:
    soup = _soup(body)

    container = _select_one(soup, ["div#orderDetails", "div#ordersContainer"]) or soup

    date_tag = _select_one(container, ORDER_DATE_SEL)
    order_date = _text(date_tag)
    if order_date:
        order_date = re.sub(r"^.*?Order [Pp]laced\s*", "", order_date).strip()

    total = None
    total_tag = _select_one(container, ORDER_TOTAL_SEL)
    total_text = _text(total_tag)
    if total_text:
        m = re.search(r"\$[\d,.]+", total_text)
        total = m.group() if m else None

    status_tag = _select_one(container, SHIPMENT_STATUS_SEL)
    status = _clean(_text(status_tag))

    delivery_date = None
    if status:
        dm = re.search(
            r"(?:Delivered|Arriving)\s+([A-Z][a-z]+ \d{1,2}(?:,\s*\d{4})?)",
            status, re.I,
        )
        delivery_date = dm.group(1) if dm else None

    addr_tag = _select_one(container, [
        "div.displayAddressDiv",
        "[data-component='shippingAddress']",
    ])
    shipping_address = _clean(_text(addr_tag))

    items = _parse_order_items(container)

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
        "url": f"{BASE}/gp/your-account/order-details?orderID={order_id}",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# IDENTITY — session check + account identity from HTML
# ═══════════════════════════════════════════════════════════════════════════════


def whoami(params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Check session liveness and extract account identity from the Your Account page."""
    params = params or {}
    cookie_header = _require_cookies(params, "whoami")

    with _auth_client(cookie_header) as client:
        _warm_session(client)
        resp = client.get(f"{BASE}/gp/css/homepage.html")

    if resp.status_code != 200:
        return {"authenticated": False, "status_code": resp.status_code}

    body = resp.text

    if "ap/signin" in resp.url.path:
        return {"authenticated": False, "redirect": str(resp.url)}

    name_match = re.search(
        r'nav-link-accountList-nav-line-1[^>]*>Hello,\s*([^<]+)<', body
    )
    customer_name_match = re.search(
        r"""\$Nav\.declare\(['"]config\.customerName['"],\s*'([^']+)'\)""", body
    )
    customer_id_match = re.search(r'"customerId"\s*:\s*"([A-Z0-9]+)"', body)
    marketplace_match = re.search(r"ue_mid\s*=\s*'([^']+)'", body)
    prime_match = re.search(r"isPrimeMember[=:]\s*['\"]?true", body, re.I)

    display = (
        name_match.group(1).strip() if name_match
        else customer_name_match.group(1).strip() if customer_name_match
        else None
    )
    customer_id = customer_id_match.group(1) if customer_id_match else None
    marketplace_id = marketplace_match.group(1) if marketplace_match else None

    return {
        "authenticated": True,
        "issuer": "amazon.com",
        "customer_id": customer_id or display,
        "display": display,
        "marketplace_id": marketplace_id,
        "is_prime": prime_match is not None,
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
