#!/usr/bin/env python3
"""
Amazon skill — search, products, order history, and account identity.

Uses Amazon's public completion.amazon.com API for keyword suggestions and
http.client for HTML page parsing. Order history and account operations
use session cookies from a browser cookie provider. No API keys required.

Transport notes (see docs/reverse-engineering/1-transport/):
- profile="navigate" — full client hints (Device-Memory, Rtt, etc.) required
  by Amazon's Lightsaber bot detection. Without these, auth pages redirect to login.
- skip_cookies=["csd-key", "csm-hit", "aws-waf-token"] — csd-key triggers Siege
  client-side encryption. Stripping it forces plain HTML responses.
- Session warming: visit homepage before order/account pages. Amazon flags direct
  deep-links from new sessions as bot traffic.
- Accept-Encoding: the engine handles brotli/gzip decompression automatically via
  reqwest feature flags. Amazon compresses large pages (~168KB order history) with
  brotli — without decompression, parsers find zero order cards in binary garbage.
"""

import json
import re
import sys
import time
from typing import Any
from urllib.parse import quote_plus

from agentos import molt, parse_int, http, get_cookies, require_cookies
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


def _extract(pattern: str, s: str, group: int = 1) -> str | None:
    m = re.search(pattern, s, re.S)
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

    resp = http.get(url, params=params)
    data = resp["json"]

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

    with http.client() as c:
        c.get(base, headers={"Accept": "text/html"})
        time.sleep(0.5)
        resp = c.get(
            f"{base}/s",
            params=search_params,
            headers={"Accept": "text/html,application/xhtml+xml"},
        )
        body = resp["body"]

    if _is_captcha(body):
        raise RuntimeError(
            "Amazon returned a CAPTCHA or block page. "
            "Try again later, or use search_suggestions which uses the JSON API with no blocking."
        )

    return _parse_search_results(body, tld)


def _parse_search_results(body: str, tld: str) -> list[dict[str, Any]]:
    soup = _soup(body)
    products: list[dict[str, Any]] = []

    for card in soup.select('div[data-asin][data-component-type="s-search-result"]'):
        asin = card.get("data-asin", "")
        if not asin or not re.match(r'^[A-Z0-9]{10}$', asin):
            continue

        # Title: h2 aria-label or h2 > span text
        h2 = card.select_one("h2")
        title = None
        if h2:
            title = h2.get("aria-label") or _text(h2)
        title = molt(title)
        if not title:
            continue

        # Price
        price_el = card.select_one(".a-price .a-offscreen")
        price = _text(price_el)

        # Rating
        rating_el = card.select_one(".a-icon-alt")
        rating = _parse_rating(_text(rating_el))

        # Rating count
        count_el = card.select_one("[class*='s-underline-text']")
        ratings_count = parse_int(_text(count_el))

        # Image
        img_el = card.select_one("img.s-image")
        image = img_el.get("src") if img_el else None

        prime = bool(card.select_one('[aria-label="Amazon Prime"]')) or bool(card.select_one(".s-prime"))
        sponsored = bool(card.select_one(".AdHolder"))

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

    with http.client() as c:
        c.get(base, headers={"Accept": "text/html"})
        time.sleep(0.5)
        resp = c.get(
            f"{base}/dp/{asin}",
            headers={"Accept": "text/html,application/xhtml+xml"},
        )
        body = resp["body"]

    if _is_captcha(body):
        raise RuntimeError("Amazon returned a CAPTCHA or block page.")

    return _parse_product_page(body, asin, tld)


def _parse_product_page(body: str, asin: str, tld: str) -> dict[str, Any]:
    soup = _soup(body)

    title = molt(_text(soup.select_one("#productTitle")))

    # Price: core price display → any offscreen price
    price_el = soup.select_one("#corePrice_feature_div .a-offscreen, #corePriceDisplay_desktop_feature_div .a-offscreen")
    if not price_el:
        price_el = soup.select_one(".a-offscreen")
    price = _text(price_el)

    rating = _parse_rating(_text(soup.select_one("#acrPopover .a-icon-alt")))
    ratings_count = parse_int(_text(soup.select_one("#acrCustomerReviewText")))

    brand_el = soup.select_one("#bylineInfo")
    brand = molt(_text(brand_el))
    if brand:
        brand = re.sub(r"^Visit the\s+", "", brand, flags=re.I)
        brand = re.sub(r"\s+Store$", "", brand, flags=re.I)
        brand = re.sub(r"^Brand:\s*", "", brand, flags=re.I)

    avail_el = soup.select_one("#availability span")
    availability = molt(_text(avail_el))

    img_el = soup.select_one("#landingImage")
    main_image = img_el.get("src") if img_el else None

    desc_el = soup.select_one("#productDescription")
    description = molt(_text(desc_el))
    if not description:
        bullets_el = soup.select_one("#feature-bullets")
        description = molt(_text(bullets_el))

    # Breadcrumb categories
    categories = [molt(_text(a)) for a in soup.select("#wayfinding-breadcrumbs_feature_div a") if molt(_text(a))]

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

_SKIP_COOKIES = ["csd-key", "csm-hit", "aws-waf-token"]


_require_cookies = require_cookies


def _warm_session(client) -> None:
    """Visit homepage first to provision session cookies and avoid bot detection on sensitive pages."""
    client.get(BASE, headers={"Sec-Fetch-Site": "none"})
    time.sleep(1.0)


def _is_login_redirect(resp: dict, body: str) -> bool:
    if "ap/signin" in str(resp["url"]):
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
    ".a-price .a-offscreen",
    "[data-component='unitPrice'] .a-text-price :not(.a-offscreen)",
    ".yohtmlc-item .a-color-price",
]
ITEM_QTY_SEL = [
    "[data-component='quantity']",
    ".item-view-qty",
]
SHIPMENT_STATUS_SEL = [
    "span.delivery-box__primary-text",
    ".yohtmlc-shipment-status-primaryText",
]
DETAIL_STATUS_SEL = SHIPMENT_STATUS_SEL + ["h4"]


def list_orders(*, filter=None, page=1, **params) -> list[dict[str, Any]]:
    """List Amazon orders from the order history page."""
    cookie_header = _require_cookies(params, "list_orders")
    order_filter = filter or "last30"
    page = int(page or 1)

    url_params: dict[str, str] = {"timeFilter": order_filter}
    if page > 1:
        url_params["startIndex"] = str((page - 1) * 10)

    with http.client(cookies=cookie_header, profile="navigate", skip_cookies=_SKIP_COOKIES, headers={"Host": "www.amazon.com"}) as c:
        _warm_session(c)

        resp = c.get(
            f"{BASE}/your-orders/orders",
            params=url_params,
            headers={"Referer": f"{BASE}/gp/homepage.html"},
        )
        body = resp["body"]

    if _is_login_redirect(resp, body):
        raise RuntimeError(
            "SESSION_EXPIRED: Amazon redirected to login — session cookies are expired or invalid."
        )

    result = _parse_order_history(body, page=page, order_filter=order_filter)
    return result["orders"]


def _parse_order_history(
    body: str, *, page: int = 1, order_filter: str = "last30",
) -> dict[str, Any]:
    soup = _soup(body)
    orders: list[dict[str, Any]] = []

    total_orders = None
    num_el = soup.select_one(".num-orders")
    if num_el:
        m = re.search(r"(\d+)", _text(num_el) or "")
        if m:
            total_orders = int(m.group(1))

    has_next = bool(soup.select("ul.a-pagination li.a-last a"))

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
            status = molt(_text(status_tag))

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

    total_pages = None
    if total_orders is not None:
        total_pages = (total_orders + 9) // 10

    return {
        "orders": orders,
        "page": page,
        "per_page": 10,
        "total_orders": total_orders,
        "total_pages": total_pages,
        "has_next": has_next,
        "filter": order_filter,
    }


def _parse_order_items(card: Tag, *, detail_page: bool = False) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen_asins: set[str] = set()

    if detail_page:
        for title_el in card.select("[data-component='itemTitle']"):
            title = molt(_text(title_el))

            container = title_el
            for _ in range(10):
                container = container.parent
                if not container or not hasattr(container, "get"):
                    break
                if "a-fixed-left-grid" in (container.get("class") or []):
                    break

            asin = None
            for a in (container or title_el.parent).select("a[href]"):
                m = re.search(r"/dp/([A-Z0-9]{10})", a.get("href", ""))
                if m:
                    asin = m.group(1)
                    break

            if not asin or asin in seen_asins:
                continue
            seen_asins.add(asin)

            price_tag = _select_one(container or title_el.parent, ITEM_PRICE_SEL)
            price = _text(price_tag)

            qty_tag = _select_one(container or title_el.parent, ITEM_QTY_SEL)
            qty_text = _text(qty_tag)
            quantity = int(qty_text) if qty_text and qty_text.isdigit() else 1

            img_tag = (container or title_el.parent).select_one("img")
            image_url = img_tag.get("src") if img_tag else None

            items.append({
                "asin": asin,
                "title": title,
                "url": f"{BASE}/dp/{asin}",
                "image_url": str(image_url) if image_url else None,
                "price": price,
                "price_amount": _parse_price(price),
                "quantity": quantity,
            })
        return items

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
        title = molt(_text(title_tag))

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
            "price_amount": _parse_price(price),
            "quantity": 1,
        })

    if not items:
        asin_titles: dict[str, str | None] = {}
        asin_images: dict[str, str | None] = {}
        for a in card.select("a[href]"):
            href = a.get("href", "")
            m = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", str(href))
            if not m:
                continue
            asin = m.group(1)
            text = a.get_text(strip=True)
            if text and asin not in asin_titles:
                asin_titles[asin] = text
            elif asin not in asin_titles:
                asin_titles.setdefault(asin, None)
            img = a.select_one("img")
            if img and asin not in asin_images:
                asin_images[asin] = str(img.get("src", ""))

        for asin, title in asin_titles.items():
            if asin in seen_asins:
                continue
            seen_asins.add(asin)
            items.append({
                "asin": asin,
                "title": title,
                "url": f"{BASE}/dp/{asin}",
                "image_url": asin_images.get(asin),
                "price": None,
                "price_amount": None,
                "quantity": 1,
            })

    return items


def buy_again(**params) -> list[dict[str, Any]]:
    """Get products Amazon recommends for repurchase."""
    cookie_header = _require_cookies(params, "buy_again")

    with http.client(cookies=cookie_header, profile="navigate", skip_cookies=_SKIP_COOKIES, headers={"Host": "www.amazon.com"}) as c:
        _warm_session(c)
        resp = c.get(
            f"{BASE}/gp/buyagain",
            headers={"Referer": f"{BASE}/your-orders/orders"},
        )
        body = resp["body"]

    if _is_login_redirect(resp, body):
        raise RuntimeError(
            "SESSION_EXPIRED: Amazon redirected to login — session cookies are expired or invalid."
        )

    return _parse_buy_again(body)


def _parse_buy_again(body: str) -> list[dict[str, Any]]:
    soup = _soup(body)
    products: list[dict[str, Any]] = []
    seen: set[str] = set()

    for el in soup.select("[data-asin]"):
        asin = el.get("data-asin", "")
        if not asin or not re.match(r"^[A-Z0-9]{10}$", asin) or asin in seen:
            continue

        title_el = (
            el.select_one("span.a-truncate-full")
            or el.select_one("[data-component='title']")
        )
        title = molt(_text(title_el))
        if not title:
            continue

        seen.add(asin)

        price_el = el.select_one(".a-price .a-offscreen")
        price = _text(price_el)

        img = el.select_one("img")
        image_url = str(img.get("src", "")) if img else None

        prime = bool(el.select_one("i.a-icon-prime"))

        badge_el = el.select_one(".a-badge-text")
        badge = _text(badge_el)

        products.append({
            "asin": asin,
            "title": title,
            "url": f"{BASE}/dp/{asin}",
            "image_url": image_url,
            "price": price,
            "price_amount": _parse_price(price),
            "prime": prime,
            "badge": badge,
        })

    return products


def subscriptions(**params) -> dict[str, Any]:
    """List active Subscribe & Save subscriptions and upcoming deliveries."""
    cookie_header = _require_cookies(params, "subscriptions")

    with http.client(cookies=cookie_header, profile="navigate", skip_cookies=_SKIP_COOKIES, headers={"Host": "www.amazon.com"}) as c:
        _warm_session(c)

        mgmt_resp = c.get(
            f"{BASE}/gp/subscribe-and-save/manager/viewsubscriptions",
            headers={"Referer": f"{BASE}/your-orders/orders"},
        )

        if _is_login_redirect(mgmt_resp, mgmt_resp["body"]):
            raise RuntimeError(
                "SESSION_EXPIRED: Amazon redirected to login — session cookies are expired or invalid."
            )

        mgmt_soup = _soup(mgmt_resp["body"])

        ship_id = None
        for tab in mgmt_soup.select("[role='tab']"):
            href = tab.get("href", "")
            m = re.search(r"shipId=([^&]+)", href)
            if m:
                ship_id = m.group(1)
                break

        deliveries: list[dict[str, Any]] = []
        for card in mgmt_soup.select(".delivery-card"):
            date_el = card.select_one("h2")
            date_text = _text(date_el) if date_el else None
            full_text = card.get_text(" ", strip=True)

            edit_deadline = None
            m = re.search(r"Last day to edit.*?:\s*(\S.*?)(?:\s*You|$)", full_text)
            if m:
                edit_deadline = m.group(1).strip()

            item_count = None
            m = re.search(r"(\d+)\s+items?\s+in\s+this\s+delivery", full_text)
            if m:
                item_count = int(m.group(1))

            if date_text:
                deliveries.append({
                    "delivery_date": date_text,
                    "edit_deadline": edit_deadline,
                    "item_count": item_count,
                })

        savings = None
        savings_el = mgmt_soup.select_one("h1")
        if savings_el:
            m = re.search(r"\$([\d,.]+)", _text(savings_el) or "")
            if m:
                savings = f"${m.group(1)}"

        items: list[dict[str, Any]] = []
        if ship_id:
            ajax_resp = c.get(
                f"{BASE}/auto-deliveries/ajax/subscriptionList",
                params={
                    "deviceType": "desktop",
                    "deviceContext": "web",
                    "shipId": ship_id,
                },
                headers={
                    "Referer": f"{BASE}/auto-deliveries/subscriptionList",
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "text/html, */*",
                },
            )
            if ajax_resp["status"] == 200:
                items = _parse_subscriptions(ajax_resp["body"])

    return {
        "total_savings": savings,
        "upcoming_deliveries": deliveries,
        "subscriptions": items,
        "subscription_count": len(items),
    }


def _parse_subscriptions(body: str) -> list[dict[str, Any]]:
    soup = _soup(body)
    items: list[dict[str, Any]] = []

    for el in soup.select("[data-subscription-id]"):
        sub_id = el.get("data-subscription-id", "")

        title_el = el.select_one("span.a-truncate-full")
        title = molt(_text(title_el))
        if not title:
            continue

        # Image: use data-a-hires or data-src (src is a placeholder pixel)
        img = el.select_one("img.sns-product-image, img")
        image_url = None
        if img:
            image_url = (
                img.get("data-a-hires")
                or img.get("data-src")
                or img.get("src", "")
            )
            if image_url and "grey-pixel" in image_url:
                image_url = None

        # Next delivery date
        next_delivery = None
        for div in el.select("div, span"):
            text = _text(div) or ""
            m = re.search(
                r"Next delivery by\s*(.+)",
                text, re.I,
            )
            if m:
                next_delivery = m.group(1).strip()
                break
        if not next_delivery:
            for span in el.select("span, div"):
                text = _text(span) or ""
                if re.match(r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2}", text) and len(text) < 30:
                    next_delivery = text
                    break

        # Frequency (e.g., "1 unit every 3 months")
        frequency = None
        for a in el.select("a.consumption-pattern-ingress-text, span.a-declarative a"):
            text = _text(a) or ""
            if re.search(r"every\s+\d+", text, re.I):
                frequency = text
                break
        if not frequency:
            for span in el.select("span, div"):
                text = _text(span) or ""
                if re.search(r"\d+\s+unit.*every", text, re.I):
                    frequency = text
                    break

        # Price (sometimes shown)
        price_el = el.select_one(".a-price .a-offscreen")
        price = _text(price_el)

        items.append({
            "subscription_id": sub_id,
            "title": title,
            "image_url": str(image_url) if image_url else None,
            "next_delivery": next_delivery,
            "frequency": frequency,
            "price": price,
            "price_amount": _parse_price(price),
        })

    return items


def get_order(*, order_id, **params) -> dict[str, Any]:
    """Fetch detailed info for a specific Amazon order."""
    cookie_header = _require_cookies(params, "get_order")
    if not order_id:
        raise ValueError("order_id is required")

    with http.client(cookies=cookie_header, profile="navigate", skip_cookies=_SKIP_COOKIES, headers={"Host": "www.amazon.com"}) as c:
        _warm_session(c)

        resp = c.get(
            f"{BASE}/gp/your-account/order-details",
            params={"orderID": order_id},
            headers={"Referer": f"{BASE}/your-orders/orders"},
        )
        body = resp["body"]

    if _is_login_redirect(resp, body):
        raise RuntimeError("SESSION_EXPIRED: Amazon redirected to login — session cookies expired.")

    return _parse_order_detail(body, order_id)


def _parse_order_detail(body: str, order_id: str) -> dict[str, Any]:
    soup = _soup(body)

    container = _select_one(soup, ["div#orderDetails", "div#ordersContainer"]) or soup

    # Order date — detail page puts it in .order-date-invoice-item directly
    order_date = None
    date_tag = _select_one(container, ORDER_DATE_SEL)
    if date_tag:
        raw = _text(date_tag) or ""
        order_date = re.sub(r"^.*?Order [Pp]laced\s*", "", raw).strip() or raw

    # Delivery status — detail page often uses <h4> with "DeliveredMarch 10" format
    status = None
    for sel_list in [SHIPMENT_STATUS_SEL, ["h4"]]:
        for sel in sel_list:
            for el in container.select(sel):
                text = _text(el) or ""
                if re.search(r"Deliver|Arriving|Shipped|Return|Cancel", text, re.I):
                    status = re.sub(r"(Delivered|Arriving)", r"\1 ", text).strip()
                    status = re.sub(r"\s{2,}", " ", status)
                    break
            if status:
                break
        if status:
            break

    delivery_date = None
    if status:
        dm = re.search(
            r"(?:Delivered|Arriving)\s+([A-Z][a-z]+ \d{1,2}(?:,\s*\d{4})?)",
            status, re.I,
        )
        delivery_date = dm.group(1) if dm else None

    # Shipping address — extract from list items, join with newlines
    shipping_address = None
    addr_tag = _select_one(container, [
        "[data-component='shippingAddress']",
        "div.displayAddressDiv",
    ])
    if addr_tag:
        parts = []
        for li in addr_tag.select("li .a-list-item"):
            text = li.get_text(separator=", ", strip=True)
            if text:
                parts.append(text)
        if parts:
            shipping_address = "\n".join(parts)
        else:
            raw_addr = _text(addr_tag) or ""
            shipping_address = re.sub(r"^Ship\s*to\s*", "", raw_addr).strip()

    # Tracking link
    track_tag = container.select_one("a[href*='track']")
    tracking_url = None
    if track_tag:
        href = track_tag.get("href", "")
        tracking_url = href if href.startswith("http") else f"{BASE}{href}"

    # Order summary from #od-subtotals
    summary: dict[str, str | None] = {}
    subtotals = container.select_one("#od-subtotals")
    if subtotals:
        for row in subtotals.select(".a-row"):
            label_el = row.select_one(".a-column.a-span7")
            value_el = row.select_one(".a-column.a-span5")
            if label_el and value_el:
                label = (_text(label_el) or "").rstrip(":").strip()
                value = _text(value_el)
                if "Subtotal" in label:
                    summary["subtotal"] = value
                elif "Shipping" in label:
                    summary["shipping"] = value
                elif "tax" in label.lower():
                    summary["tax"] = value
                elif "Grand Total" in label:
                    summary["grand_total"] = value
                elif "saving" in label.lower() or "discount" in label.lower():
                    summary["discount"] = value

    total = summary.get("grand_total")
    if not total:
        total_tag = _select_one(container, ORDER_TOTAL_SEL)
        total_text = _text(total_tag)
        if total_text:
            m = re.search(r"\$[\d,.]+", total_text)
            total = m.group() if m else None

    items = _parse_order_items(container, detail_page=True)

    return {
        "order_id": order_id,
        "order_date": order_date,
        "total": total,
        "total_amount": _parse_price(total),
        "status": status,
        "delivery_date": delivery_date,
        "shipping_address": shipping_address,
        "tracking_url": tracking_url,
        "summary": summary or None,
        "item_count": len(items),
        "items": items,
        "url": f"{BASE}/gp/your-account/order-details?orderID={order_id}",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# LISTS — wishlists, shopping lists, idea lists
# ═══════════════════════════════════════════════════════════════════════════════

LIST_NAV_SEL = [
    "#your-lists-nav .wl-list",
    ".wl-list",
]

LIST_ITEM_SEL = [
    "li.g-item-sortable[data-itemid]",
    "li[data-itemid]",
]

ITEM_TITLE_SEL = [
    "a[id^='itemName_']",
    "h2 a.a-link-normal[title]",
]

ITEM_PRICE_SEL = [
    ".price-section .a-price .a-offscreen",
    ".a-price .a-offscreen",
]

ITEM_RATING_SEL = [
    ".a-icon-star-small span.a-icon-alt",
    "i.a-icon-star-small span.a-icon-alt",
]

ITEM_REVIEW_COUNT_SEL = [
    "a[id^='review_count_']",
    "a.a-link-normal[aria-label]",
]

MAX_LIST_PAGES = 20


def list_lists(**params) -> list[dict[str, Any]]:
    """List all of the user's Amazon lists (wishlists, shopping lists, etc.)."""
    cookie_header = _require_cookies(params, "list_lists")

    with http.client(cookies=cookie_header, profile="navigate", skip_cookies=_SKIP_COOKIES, headers={"Host": "www.amazon.com"}) as c:
        _warm_session(c)
        resp = c.get(
            f"{BASE}/hz/wishlist/ls",
            headers={"Referer": BASE},
        )
        body = resp["body"]

    if _is_login_redirect(resp, body):
        raise RuntimeError(
            "SESSION_EXPIRED: Amazon redirected to login — session cookies are expired or invalid."
        )

    return _parse_lists_nav(body)


def _parse_lists_nav(body: str) -> list[dict[str, Any]]:
    soup = _soup(body)
    lists: list[dict[str, Any]] = []

    for entry in _select(soup, LIST_NAV_SEL):
        link = entry.select_one("a[id^='wl-list-link-']")
        if not link:
            continue

        link_id = (link.get("id") or "").replace("wl-list-link-", "")
        if not link_id:
            continue

        title_el = entry.select_one("span[id^='wl-list-entry-title-']")
        name = _text(title_el) or "Untitled List"

        privacy_el = entry.select_one(".wl-list-entry-privacy span")
        privacy = _text(privacy_el)

        is_default = bool(entry.select_one("#list-default-collaborator-label"))
        is_selected = "selected" in (entry.get("class") or [])

        list_type = None
        href = link.get("href", "")
        if "type=" in href:
            m = re.search(r"type=([^&]+)", href)
            if m:
                list_type = m.group(1)

        lists.append({
            "list_id": link_id,
            "name": name,
            "url": f"{BASE}/hz/wishlist/ls/{link_id}",
            "privacy": privacy,
            "is_default": is_default,
            "list_type": list_type or "WishList",
        })

    return lists


def get_list(*, list_id, filter=None, **params) -> dict[str, Any]:
    """Get items from a specific Amazon list by list ID."""
    cookie_header = _require_cookies(params, "get_list")
    if not list_id:
        raise ValueError("get_list requires a list_id parameter")
    item_filter = filter or "unpurchased"

    all_items: list[dict[str, Any]] = []
    seen: set[str] = set()
    list_name = None
    list_privacy = None
    list_type = None

    with http.client(cookies=cookie_header, profile="navigate", skip_cookies=_SKIP_COOKIES, headers={"Host": "www.amazon.com"}) as c:
        _warm_session(c)

        resp = c.get(
            f"{BASE}/hz/wishlist/ls/{list_id}",
            params={"filter": item_filter, "sort": "date-added", "viewType": "list"},
            headers={"Referer": BASE},
        )
        body = resp["body"]

        if _is_login_redirect(resp, body):
            raise RuntimeError(
                "SESSION_EXPIRED: Amazon redirected to login — session cookies are expired or invalid."
            )

        soup = _soup(body)

        name_el = soup.select_one("#profile-list-name")
        list_name = _text(name_el) or "Wish List"

        privacy_el = soup.select_one("#listPrivacy")
        list_privacy = _text(privacy_el)

        remember_state = _extract_a_state(soup, "rememberState")
        if remember_state:
            list_type = remember_state.get("listType")

        page_items = _parse_list_items(soup)
        for item in page_items:
            if item["asin"] not in seen:
                seen.add(item["asin"])
                all_items.append(item)

        for _ in range(MAX_LIST_PAGES - 1):
            scroll_state = _extract_a_state(soup, "scrollState")
            if not scroll_state:
                break
            show_more = scroll_state.get("showMoreUrl")
            if not show_more:
                break

            time.sleep(1.0)
            ajax_resp = c.get(
                f"{BASE}{show_more}" if show_more.startswith("/") else show_more,
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": f"{BASE}/hz/wishlist/ls/{list_id}",
                },
            )
            if ajax_resp["status"] != 200:
                break

            ajax_body = ajax_resp["body"]
            ajax_soup = _soup(ajax_body)

            page_items = _parse_list_items(ajax_soup)
            if not page_items:
                break

            new_count = 0
            for item in page_items:
                if item["asin"] not in seen:
                    seen.add(item["asin"])
                    all_items.append(item)
                    new_count += 1
            if new_count == 0:
                break

            soup = ajax_soup

    return {
        "list_id": list_id,
        "name": list_name,
        "url": f"{BASE}/hz/wishlist/ls/{list_id}",
        "privacy": list_privacy,
        "list_type": list_type,
        "item_count": len(all_items),
        "items": all_items,
    }


def _extract_a_state(soup: BeautifulSoup, key: str) -> dict[str, Any] | None:
    for script in soup.select('script[type="a-state"]'):
        try:
            state_meta = json.loads(script.get("data-a-state", "{}"))
            if state_meta.get("key") == key:
                return json.loads(script.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def _parse_list_items(soup: BeautifulSoup) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for li in _select(soup, LIST_ITEM_SEL):
        item_id = li.get("data-itemid", "")
        if not item_id:
            continue

        asin = None
        repo_params_str = li.get("data-reposition-action-params", "")
        if repo_params_str:
            try:
                repo = json.loads(repo_params_str)
                ext_id = repo.get("itemExternalId", "")
                m = re.match(r"ASIN:([A-Z0-9]{10})", ext_id)
                if m:
                    asin = m.group(1)
            except (json.JSONDecodeError, TypeError):
                pass

        title_el = _select_one(li, ITEM_TITLE_SEL)
        title = None
        if title_el:
            title = title_el.get("title") or _text(title_el)
            if not asin:
                href = title_el.get("href", "")
                m = re.search(r"/dp/([A-Z0-9]{10})", href)
                if m:
                    asin = m.group(1)

        if not asin:
            continue

        price_el = _select_one(li, ITEM_PRICE_SEL)
        price = _text(price_el)

        byline_el = li.select_one(f"span[id^='item-byline-']")
        byline = _text(byline_el)

        rating_el = _select_one(li, ITEM_RATING_SEL)
        rating_text = _text(rating_el)

        review_el = _select_one(li, ITEM_REVIEW_COUNT_SEL)
        review_text = _text(review_el)
        review_count = None
        if review_text:
            clean = re.sub(r"[^\d]", "", review_text)
            review_count = int(clean) if clean else None

        img_el = li.select_one(f"#itemImage_{item_id} img") or li.select_one("img[alt]")
        image_url = str(img_el.get("src", "")) if img_el else None

        date_el = li.select_one(f"span[id^='itemAddedDate_']")
        date_added = _text(date_el)
        if date_added:
            date_added = re.sub(r"^Item added\s*", "", date_added).strip()

        priority_el = li.select_one(f"span[id^='itemPriorityLabel_']")
        priority = _text(priority_el)

        comment_el = li.select_one(f"span[id^='itemComment_']")
        comment = _text(comment_el)

        items.append({
            "asin": asin,
            "title": molt(title),
            "url": f"{BASE}/dp/{asin}",
            "image_url": image_url,
            "byline": molt(byline),
            "price": price,
            "price_amount": _parse_price(price),
            "rating": _parse_rating(rating_text),
            "ratings_count": review_count,
            "date_added": date_added,
            "priority": priority,
            "comment": comment if comment else None,
        })

    return items


# ═══════════════════════════════════════════════════════════════════════════════
# IDENTITY — session check + account identity from HTML
# ═══════════════════════════════════════════════════════════════════════════════


def whoami(**params) -> dict[str, Any]:
    """Check session liveness and extract account identity.

    Fetches two pages:
    1. /gp/css/homepage.html — nav bar display name, customerId, marketplace, Prime status
    2. /ax/account/manage  — Login & Security page, contains the account email

    The email is the canonical identifier (unique per Amazon account).
    """
    cookie_header = _require_cookies(params, "whoami")

    with http.client(cookies=cookie_header, profile="navigate", skip_cookies=_SKIP_COOKIES, headers={"Host": "www.amazon.com"}) as c:
        _warm_session(c)
        resp = c.get(f"{BASE}/gp/css/homepage.html")

        if resp["status"] != 200:
            return {"authenticated": False, "status_code": resp["status"]}

        body = resp["body"]

        if "ap/signin" in str(resp["url"]):
            return {"authenticated": False, "redirect": str(resp["url"])}

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

        # Fetch Login & Security page to get the account email.
        email = None
        manage_resp = c.get(f"{BASE}/ax/account/manage")
        if manage_resp["status"] == 200 and "ap/signin" not in str(manage_resp["url"]):
            email_match = re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", manage_resp["body"])
            if email_match:
                email = email_match.group(0)

    return {
        "authenticated": True,
        "domain": "amazon.com",
        "identifier": email or customer_id or display,
        "customer_id": customer_id,
        "display": display,
        "email": email,
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
