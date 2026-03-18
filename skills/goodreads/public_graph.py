#!/usr/bin/env python3

import html
import json
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError


USER_AGENT = "Mozilla/5.0 (compatible; AgentOS/1.0)"
BASE_URL = "https://www.goodreads.com"
FALLBACK_GRAPHQL_ENDPOINT = (
    "https://kxbwmqov6jgg3daaamb744ycu4.appsync-api.us-east-1.amazonaws.com/graphql"
)
FALLBACK_GRAPHQL_API_KEY = "da2-xpgsdydkbregjhpr6ejzqdhuwy"
APPSYNC_ENDPOINT_RE = re.compile(
    r'"graphql":\{"apiKey":"(da2-[a-z0-9]+)","endpoint":"(https://[a-z0-9]+\.appsync-api\.[a-z0-9-]+\.amazonaws\.com/graphql)"'
)
APP_BUNDLE_RE = re.compile(r'/_next/static/chunks/pages/_app-[a-f0-9]+\.js')


def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    return fetch_url(url, headers=headers).decode("utf-8", errors="replace")


def fetch_url(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    method: str | None = None,
) -> bytes:
    last_error = None
    request_headers = headers or {}
    request_method = method or ("POST" if data is not None else "GET")
    for attempt in range(4):
        request = urllib.request.Request(
            url,
            data=data,
            headers=request_headers,
            method=request_method,
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except HTTPError as error:
            last_error = error
            if error.code not in {429, 500, 502, 503, 504} or attempt == 3:
                raise
        except URLError as error:
            last_error = error
            if attempt == 3:
                raise
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed Goodreads request: {last_error}")


def clean_html_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</p\s*>", "\n\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    value = re.sub(r"[ \t\f\v]+", " ", value)
    value = re.sub(r"\n[ \t]+", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    value = value.strip()
    return value or None


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def absolute_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return f"{BASE_URL}{url}"


def parse_int(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else None


def iso_from_ms(value: Any) -> str | None:
    if not isinstance(value, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()
    except (ValueError, OSError):
        return None


def first_match(pattern: str, text: str, flags: int = re.S) -> str | None:
    match = re.search(pattern, text, flags)
    return match.group(1) if match else None


def unique_by(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen = set()
    deduped = []
    for item in items:
        value = item.get(key)
        if value in seen:
            continue
        seen.add(value)
        deduped.append(item)
    return deduped


def extract_next_data(html_text: str) -> dict[str, Any]:
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html_text,
        re.S,
    )
    if not match:
        raise RuntimeError("Could not find __NEXT_DATA__ in Goodreads page")
    return json.loads(match.group(1))


def deref(apollo: dict[str, Any], value: Any) -> Any:
    if isinstance(value, dict) and "__ref" in value:
        return apollo.get(value["__ref"])
    return value


def parse_review_id(review: dict[str, Any]) -> str | None:
    review_url = (((review.get("shelving") or {}).get("webUrl")) or "")
    match = re.search(r"/review/show/([0-9]+)", review_url)
    if match:
        return match.group(1)
    review_id = review.get("id")
    return str(review_id) if review_id else None


def _make_runtime(endpoint: str, api_key: str, source: str) -> dict[str, Any]:
    return {
        "graphql_endpoint": endpoint,
        "x_api_key": api_key,
        "source": source,
        "headers": {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            "x-api-key": api_key,
        },
    }


def discover_from_bundle(html_text: str) -> dict[str, Any] | None:
    """Extract AppSync config from the Next.js _app JS bundle.

    Goodreads ships environment configs (Dev, Beta, Preprod, Prod) as inline
    JSON inside their _app chunk.  We fetch that chunk and pick the Prod entry
    by looking for the last graphql config block — Prod is always last in the
    build output, identified by "shortName":"Prod" in the surrounding context.
    """
    bundle_match = APP_BUNDLE_RE.search(html_text)
    if not bundle_match:
        return None

    try:
        bundle_js = fetch_url(
            f"{BASE_URL}{bundle_match.group()}",
            headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
        ).decode("utf-8", errors="replace")
    except (HTTPError, URLError, OSError):
        return None

    configs: list[tuple[str, str, str]] = []
    for m in APPSYNC_ENDPOINT_RE.finditer(bundle_js):
        api_key = m.group(1)
        endpoint = m.group(2)
        # Grab the shortName from surrounding context
        tail = bundle_js[m.end() : m.end() + 200]
        name_match = re.search(r'"shortName":"([^"]+)"', tail)
        short_name = name_match.group(1) if name_match else ""
        configs.append((short_name, api_key, endpoint))

    prod = next(((k, e) for n, k, e in configs if n == "Prod"), None)
    if prod:
        return _make_runtime(prod[1], prod[0], "js_bundle_discovery")

    if configs:
        _, api_key, endpoint = configs[-1]
        return _make_runtime(endpoint, api_key, "js_bundle_discovery")

    return None


def discover_via_browser(page_url: str) -> dict[str, Any] | None:
    """Fallback: launch a stealth headless browser and capture AppSync traffic."""
    script = r"""
const { chromium } = require("playwright");
(async () => {
  const targetUrl = process.argv[1];
  const pattern = /appsync-api.*\.amazonaws\.com\/graphql/;
  const browser = await chromium.launch({
    headless: true,
    args: ["--disable-blink-features=AutomationControlled"],
  });
  const context = await browser.newContext({
    userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    viewport: { width: 1440, height: 900 },
    locale: "en-US",
    timezoneId: "America/New_York",
  });
  const page = await context.newPage();
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "webdriver", { get: () => false });
  });
  const captured = [];
  page.on("request", (req) => {
    if (!pattern.test(req.url())) return;
    captured.push({ url: req.url(), headers: req.headers() });
  });
  try {
    await page.goto(targetUrl, { waitUntil: "domcontentloaded", timeout: 30000 });
  } catch {}
  await page.waitForTimeout(15000);
  await browser.close();
  console.log(JSON.stringify(captured));
})().catch((e) => {
  console.error(e && e.stack ? e.stack : String(e));
  process.exit(1);
});
""".strip()

    try:
        result = subprocess.run(
            ["node", "-e", script, page_url],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        return None

    if result.returncode != 0 or not result.stdout.strip():
        return None

    try:
        captured = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

    if not isinstance(captured, list) or not captured:
        return None

    first = captured[0] or {}
    headers = first.get("headers") or {}
    api_key = headers.get("x-api-key") or headers.get("X-Api-Key") or ""
    endpoint = first.get("url")
    if not endpoint or not api_key:
        return None

    return _make_runtime(endpoint, api_key, "browser_network_capture")


def discover_runtime(
    *,
    html_text: str | None = None,
    page_url: str | None = None,
    cache: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    """Resolve AppSync transport config.

    Priority: graph cache → JS bundle extraction → browser capture → hardcoded fallback.
    Returns (runtime, was_cached) — callers use was_cached to decide whether to
    write back via __cache__.
    """
    if cache and cache.get("graphql_endpoint") and cache.get("x_api_key"):
        return _make_runtime(
            cache["graphql_endpoint"],
            cache["x_api_key"],
            cache.get("source", "graph_cache"),
        ), True

    if html_text:
        runtime = discover_from_bundle(html_text)
        if runtime:
            return runtime, False

    if page_url:
        try:
            html_text = fetch_html(page_url)
            runtime = discover_from_bundle(html_text)
            if runtime:
                return runtime, False
        except (HTTPError, URLError, OSError):
            pass

        runtime = discover_via_browser(page_url)
        if runtime:
            return runtime, False

    return _make_runtime(
        FALLBACK_GRAPHQL_ENDPOINT,
        FALLBACK_GRAPHQL_API_KEY,
        "hardcoded_fallback",
    ), False


def _wrap_result(result: Any, runtime: dict[str, Any], was_cached: bool) -> Any:
    """If runtime was freshly discovered, wrap the result with __cache__ for
    graph-backed persistence. Otherwise return the result unchanged."""
    if was_cached:
        return result
    return {
        "__cache__": {
            "graphql_endpoint": runtime["graphql_endpoint"],
            "x_api_key": runtime["x_api_key"],
            "source": runtime.get("source", "discovered"),
        },
        "__result__": result,
    }


def graphql_request(
    query: str,
    variables: dict[str, Any],
    runtime: dict[str, Any],
    *,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Send a GraphQL request. Pass extra_headers (e.g. Cookie) for authenticated calls."""
    headers = dict(runtime["headers"])
    if extra_headers:
        headers.update(extra_headers)
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    body = fetch_url(
        runtime["graphql_endpoint"],
        headers=headers,
        data=payload,
        method="POST",
    )
    parsed = json.loads(body.decode("utf-8", errors="replace"))
    errors = parsed.get("errors") or []
    if errors:
        messages = "; ".join(error.get("message", "Unknown GraphQL error") for error in errors)
        raise RuntimeError(messages)
    return parsed.get("data") or {}


# Minimal auth-required query to validate session (see docs/reverse-engineering/2-discovery.md).
GET_VIEWER_QUERY = """
query getViewer {
  getViewer {
    __typename
    id
    legacyId
    name
  }
}
""".strip()


def get_viewer(runtime: dict[str, Any], cookie_header: str) -> dict[str, Any]:
    """Fetch the current viewer (logged-in user) via GraphQL with session cookies."""
    data = graphql_request(
        GET_VIEWER_QUERY,
        {},
        runtime,
        extra_headers={"Cookie": cookie_header},
    )
    return (data.get("getViewer") or {}) if isinstance(data, dict) else {}


def load_book_page(book_id: str) -> dict[str, Any]:
    url = f"{BASE_URL}/book/show/{book_id}"
    html_text = fetch_html(url)
    next_data = extract_next_data(html_text)
    page_props = next_data.get("props", {}).get("pageProps", {}) or {}
    apollo = page_props.get("apolloState", {}) or {}
    root_query = apollo.get("ROOT_QUERY", {}) or {}

    book_ref = root_query.get(f'getBookByLegacyId({{"legacyId":"{book_id}"}})', {}).get("__ref")
    if not book_ref or book_ref not in apollo:
        raise RuntimeError(f"Could not resolve public Goodreads book {book_id}")

    book = apollo[book_ref]
    work = deref(apollo, book.get("work"))
    work_details = deref(work, work.get("details") if work else None)
    work_stats = deref(work, work.get("stats") if work else None)
    return {
        "url": url,
        "html": html_text,
        "next_data": next_data,
        "page_props": page_props,
        "apollo": apollo,
        "root_query": root_query,
        "book": book,
        "work": work,
        "work_details": work_details,
        "work_stats": work_stats,
    }


def map_book_payload(page: dict[str, Any]) -> dict[str, Any]:
    apollo = page["apollo"]
    root_query = page["root_query"]
    book = page["book"]
    work_details = page["work_details"] or {}
    work_stats = page["work_stats"] or {}
    details = book.get("details") or {}

    primary_edge = book.get("primaryContributorEdge") or {}
    primary_contributor = deref(apollo, primary_edge.get("node") or {}) or {}

    contributors = []
    for edge in [primary_edge, *(book.get("secondaryContributorEdges") or [])]:
        contributor = deref(apollo, edge.get("node") or {}) or {}
        if not contributor:
            continue
        contributors.append(
            {
                "author_id": contributor.get("legacyId"),
                "name": contributor.get("name"),
                "url": contributor.get("webUrl"),
                "image_url": contributor.get("profileImageUrl"),
                "role": edge.get("role"),
            }
        )

    genres = []
    for item in book.get("bookGenres") or []:
        genre = item.get("genre") or {}
        if genre.get("name"):
            genres.append(genre.get("name"))

    series = []
    for item in book.get("bookSeries") or []:
        series_name = ((item.get("series") or {}).get("title")) or item.get("title")
        if series_name:
            series.append(series_name)

    social_signals = root_query.get(
        f'getSocialSignals({{"bookId":"{book.get("id")}","shelfStatus":["CURRENTLY_READING","TO_READ"]}})',
        [],
    )
    social_counts: dict[str, int] = {}
    for signal in social_signals or []:
        name = signal.get("name")
        count = signal.get("count")
        if name and count is not None:
            social_counts[name] = count

    places = [item.get("name") for item in work_details.get("places") or [] if item.get("name")]
    characters = [item.get("name") for item in work_details.get("characters") or [] if item.get("name")]
    awards = [
        item.get("name")
        for item in work_details.get("awardsWon") or []
        if isinstance(item, dict) and item.get("name")
    ]

    return {
        "book_id": book.get("legacyId"),
        "title": book.get("title"),
        "description": book.get('description({"stripped":true})') or book.get("description"),
        "cover_url": book.get("imageUrl"),
        "primary_author": primary_contributor.get("name"),
        "primary_author_id": primary_contributor.get("legacyId"),
        "primary_author_url": primary_contributor.get("webUrl"),
        "isbn": details.get("isbn"),
        "isbn13": details.get("isbn13"),
        "publication_date": iso_from_ms(details.get("publicationTime") or work_details.get("publicationTime")),
        "average_rating": work_stats.get("averageRating"),
        "ratings_count": work_stats.get("ratingsCount"),
        "review_count": work_stats.get("textReviewsCount"),
        "pages": details.get("numPages"),
        "genres": genres,
        "series_name": series[0] if series else None,
        "series": series,
        "publisher": details.get("publisher"),
        "format": details.get("format"),
        "language": ((details.get("language") or {}).get("name")),
        "web_url": book.get("webUrl"),
        "work_url": work_details.get("webUrl"),
        "original_title": work_details.get("originalTitle"),
        "currently_reading_count": social_counts.get("CURRENTLY_READING"),
        "to_read_count": social_counts.get("TO_READ"),
        "contributors": unique_by(contributors, "name"),
    }


def map_review_list(apollo: dict[str, Any], edges: list[dict[str, Any]], book: dict[str, Any]) -> list[dict[str, Any]]:
    reviews = []
    for edge in edges:
        review = deref(apollo, (edge.get("node") or {}))
        if not review:
            continue
        creator = deref(apollo, review.get("creator")) or {}
        shelving = review.get("shelving") or {}
        shelf = shelving.get("shelf") or {}
        taggings = shelving.get("taggings") or []
        tags = [
            ((tagging.get("tag") or {}).get("name"))
            for tagging in taggings
            if (tagging.get("tag") or {}).get("name")
        ]
        reviews.append(
            {
                "review_id": parse_review_id(review),
                "book_id": book.get("legacyId"),
                "book_title": book.get("title"),
                "review_text": review.get("text"),
                "review_date": iso_from_ms(review.get("createdAt")),
                "review_updated_at": iso_from_ms(review.get("updatedAt")),
                "rating": review.get("rating"),
                "likes_count": review.get("likeCount"),
                "comment_count": review.get("commentCount"),
                "reviewer_id": creator.get("legacyId") or creator.get("id"),
                "reviewer_name": creator.get("name"),
                "reviewer_url": creator.get("webUrl"),
                "reviewer_image_url": creator.get("imageUrlSquare"),
                "reviewer_followers_count": creator.get("followersCount"),
                "reviewer_reviews_count": creator.get("textReviewsCount"),
                "shelf_name": shelf.get("name"),
                "shelf_display_name": shelf.get("displayName"),
                "review_url": shelving.get("webUrl"),
                "tags": tags,
            }
        )
    return reviews


def get_public_book(book_id: str) -> dict[str, Any]:
    return map_book_payload(load_book_page(book_id))


def list_book_reviews(book_id: str, limit: int, cache: dict[str, Any] | None = None) -> Any:
    page = load_book_page(book_id)
    work = page["work"] or {}
    work_id = work.get("id")
    apollo = page["apollo"]
    book = page["book"]
    if not work_id:
        edges = (((page["root_query"].get("getReviews") or {}).get("edges")) or [])
        return map_review_list(apollo, edges, book)

    query = """
fragment SocialUserFragment on User {
  followersCount
}

fragment ReviewerProfileFragment on User {
  id: legacyId
  imageUrlSquare
  textReviewsCount
  name
  webUrl
  ...SocialUserFragment
}

fragment ReviewCardFragment on Review {
  id
  creator {
    ...ReviewerProfileFragment
  }
  updatedAt
  createdAt
  text
  rating
  shelving {
    shelf {
      name
      displayName
    }
    taggings {
      tag {
        name
      }
    }
    webUrl
  }
  likeCount
  commentCount
}

query getReviews($filters: BookReviewsFilterInput!, $pagination: PaginationInput) {
  getReviews(filters: $filters, pagination: $pagination) {
    edges {
      node {
        ...ReviewCardFragment
      }
    }
  }
}
""".strip()
    runtime, was_cached = discover_runtime(html_text=page["html"], page_url=page["url"], cache=cache)
    data = graphql_request(
        query,
        {
            "filters": {"resourceType": "WORK", "resourceId": work_id},
            "pagination": {"limit": limit},
        },
        runtime,
    )
    edges = (((data.get("getReviews") or {}).get("edges")) or [])
    reviews = map_review_list(apollo, edges, book)
    return _wrap_result(reviews, runtime, was_cached)


def list_similar_books(book_id: str, limit: int, cache: dict[str, Any] | None = None) -> Any:
    page = load_book_page(book_id)
    book = page["book"]
    query = """
query getSimilarBooks($id: ID!, $limit: Int!) {
  getSimilarBooks(id: $id, pagination: { limit: $limit }) {
    edges {
      node {
        title
        imageUrl
        webUrl
        primaryContributorEdge {
          node {
            name
          }
        }
        work {
          stats {
            averageRating
            ratingsCount
          }
        }
      }
    }
  }
}
""".strip()
    runtime, was_cached = discover_runtime(html_text=page["html"], page_url=page["url"], cache=cache)
    data = graphql_request(query, {"id": book.get("id"), "limit": limit}, runtime)
    edges = (((data.get("getSimilarBooks") or {}).get("edges")) or [])
    books = []
    for edge in edges:
        node = edge.get("node") or {}
        web_url = node.get("webUrl")
        match = re.search(r"/book/show/([0-9]+)", web_url or "")
        books.append(
            {
                "book_id": int(match.group(1)) if match else web_url,
                "title": node.get("title"),
                "cover_url": node.get("imageUrl"),
                "primary_author": (((node.get("primaryContributorEdge") or {}).get("node")) or {}).get("name"),
                "average_rating": ((((node.get("work") or {}).get("stats")) or {}).get("averageRating")),
                "ratings_count": ((((node.get("work") or {}).get("stats")) or {}).get("ratingsCount")),
                "web_url": web_url,
            }
        )
    return _wrap_result(books, runtime, was_cached)


def search_books(query: str, limit: int, cache: dict[str, Any] | None = None) -> Any:
    """Search books via the public AppSync getSearchSuggestions endpoint."""
    gql = """
query getSearchSuggestions($searchQuery: String!) {
  getSearchSuggestions(query: $searchQuery) {
    edges {
      ... on SearchBookEdge {
        node {
          id
          title
          primaryContributorEdge {
            node { name isGrAuthor legacyId }
          }
          webUrl
          imageUrl
        }
      }
    }
  }
}
""".strip()
    runtime, was_cached = discover_runtime(page_url=f"{BASE_URL}/book/show/1", cache=cache)
    data = graphql_request(gql, {"searchQuery": query}, runtime)
    edges = (((data.get("getSearchSuggestions") or {}).get("edges")) or [])
    books = []
    for edge in edges[:limit]:
        node = edge.get("node") or {}
        if not node:
            continue
        web_url = node.get("webUrl") or ""
        match = re.search(r"/book/show/([0-9]+)", web_url)
        contributor = ((node.get("primaryContributorEdge") or {}).get("node")) or {}
        books.append(
            {
                "book_id": int(match.group(1)) if match else None,
                "title": node.get("title"),
                "cover_url": node.get("imageUrl"),
                "primary_author": contributor.get("name"),
                "primary_author_id": contributor.get("legacyId"),
                "web_url": web_url,
            }
        )
    return _wrap_result(books, runtime, was_cached)


def list_series_books(book_id: str, limit: int, cache: dict[str, Any] | None = None) -> Any:
    """List all books in a series, given any book_id that belongs to a series."""
    page = load_book_page(book_id)
    apollo = page["apollo"]
    book = page["book"]

    series_id = None
    for item in book.get("bookSeries") or []:
        series_ref = item.get("series")
        series_obj = deref(apollo, series_ref) if series_ref else None
        if series_obj and series_obj.get("id"):
            series_id = series_obj["id"]
            break

    if not series_id:
        return []

    gql = """
query getWorksForSeries($input: GetWorksForSeriesInput!, $pagination: PaginationInput) {
  getWorksForSeries(getWorksForSeriesInput: $input, pagination: $pagination) {
    edges {
      seriesPlacement
      isPrimary
      node {
        id
        stats { averageRating ratingsCount }
        bestBook {
          title imageUrl webUrl legacyId
          primaryContributorEdge { node { name legacyId } }
        }
      }
    }
  }
}
""".strip()
    runtime, was_cached = discover_runtime(html_text=page["html"], page_url=page["url"], cache=cache)
    data = graphql_request(gql, {"input": {"id": series_id}, "pagination": {"limit": limit}}, runtime)
    edges = (((data.get("getWorksForSeries") or {}).get("edges")) or [])
    books = []
    for edge in edges:
        node = edge.get("node") or {}
        best = node.get("bestBook") or {}
        contributor = ((best.get("primaryContributorEdge") or {}).get("node")) or {}
        stats = node.get("stats") or {}
        books.append(
            {
                "book_id": best.get("legacyId"),
                "title": best.get("title"),
                "cover_url": best.get("imageUrl"),
                "web_url": best.get("webUrl"),
                "primary_author": contributor.get("name"),
                "primary_author_id": contributor.get("legacyId"),
                "average_rating": stats.get("averageRating"),
                "ratings_count": stats.get("ratingsCount"),
                "series_placement": edge.get("seriesPlacement"),
                "is_primary": edge.get("isPrimary"),
            }
        )
    return _wrap_result(books, runtime, was_cached)


def section_between(html_text: str, start_marker: str, end_marker: str) -> str:
    start = html_text.find(start_marker)
    if start == -1:
        return ""
    end = html_text.find(end_marker, start)
    if end == -1:
        return html_text[start:]
    return html_text[start:end]


def parse_profile_favorite_books(html_text: str, limit: int) -> list[dict[str, Any]]:
    section = section_between(html_text, '<div id="featured_shelf"', '<div class="bigBoxBottom"></div></div>')
    books = []
    for href, alt, image in re.findall(
        r'<a href="(/book/show/[^"]+)"><img alt="([^"]+)"[^>]*src="([^"]+)"',
        section,
        re.S,
    ):
        title = clean_text(alt) or ""
        author = None
        if " by " in title:
            title, author = title.rsplit(" by ", 1)
        books.append(
            {
                "book_id": parse_int(first_match(r"/book/show/([0-9]+)", href)),
                "title": title,
                "primary_author": author,
                "cover_url": image,
                "web_url": absolute_url(href),
            }
        )
        if len(books) >= limit:
            break
    return unique_by(books, "book_id")


def parse_profile_shelves(html_text: str, user_id: int, limit: int) -> list[dict[str, Any]]:
    section = first_match(r'<div id="shelves">(.*?)</div>\s*<br class="clear"/>', html_text)
    if not section:
        return []
    shelves = []
    for href, shelf_name, label, count in re.findall(
        r'<a class="actionLinkLite userShowPageShelfListItem" href="(/review/list/\d+\?shelf=([^"]+))">\s*([^<]+)&lrm;\s*\(([\d,]+)\)',
        section,
        re.S,
    ):
        shelves.append(
            {
                "shelf_id": f"{user_id}:{html.unescape(shelf_name)}",
                "name": clean_text(label),
                "book_count": parse_int(count),
                "url": absolute_url(href),
            }
        )
        if len(shelves) >= limit:
            break
    return unique_by(shelves, "shelf_id")


def parse_profile_currently_reading(html_text: str, limit: int) -> list[dict[str, Any]]:
    marker = 'id="currentlyReadingReviews"'
    start = html_text.find(marker)
    if start == -1:
        return []
    section = html_text[start : start + 12000]
    books = []
    pattern = re.compile(
        r'<div class="Updates no_border">.*?'
        r'<a title="[^"]+" href="(?P<book_href>/book/show/[^"]+)"><img alt="[^"]+" src="(?P<cover>[^"]+)"'
        r'.*?<a class="bookTitle" href="(?P<book_href_2>/book/show/[^"]+)">(?P<title>.*?)</a>'
        r'.*?<a class="authorName" href="(?P<author_href>/author/show/[^"]+)">(?P<author_name>.*?)</a>',
        re.S,
    )
    for match in pattern.finditer(section):
        books.append(
            {
                "book_id": parse_int(first_match(r"/book/show/([0-9]+)", match.group("book_href"))),
                "title": clean_html_text(match.group("title")),
                "cover_url": match.group("cover"),
                "web_url": absolute_url(match.group("book_href")),
                "primary_author": clean_html_text(match.group("author_name")),
                "primary_author_id": parse_int(first_match(r"/author/show/([0-9]+)", match.group("author_href"))),
                "primary_author_url": absolute_url(match.group("author_href")),
            }
        )
        if len(books) >= limit:
            break
    return unique_by(books, "book_id")


def get_public_profile(user_id: str, limit: int) -> dict[str, Any]:
    html_text = fetch_html(f"{BASE_URL}/user/show/{user_id}")
    title = clean_text(first_match(r"<title>(.*?)</title>", html_text)) or ""
    title_match = re.match(r"^(.*?) \((.*?)\) - (.*?) \(([\d,]+) books\)$", title)
    name = clean_html_text(first_match(r'<h1 id="profileNameTopHeading"[^>]*>(.*?)</h1>', html_text))
    username = first_match(r'<meta property="profile:username" content="([^"]+)"', html_text)
    ratings_count = parse_int(first_match(r'>([\d,]+) ratings</a>', html_text))
    avg_rating = first_match(r"\(([\d.]+) avg\)", html_text)
    reviews_count = parse_int(
        first_match(r'view=reviews">\s*([\d,]+) reviews', html_text)
        or first_match(r"([\d,]+) reviews", html_text)
    )
    photo_url = first_match(r'<meta property="og:image" content="([^"]+)"', html_text)
    website = first_match(r'<a rel="me noopener noreferrer"[^>]*href="([^"]+)"', html_text)

    return {
        "user_id": parse_int(user_id),
        "name": name or (title_match.group(1) if title_match else None),
        "username": username or (title_match.group(2) if title_match else None),
        "location": title_match.group(3) if title_match else None,
        "books_count": parse_int(title_match.group(4) if title_match else None),
        "ratings_count": ratings_count,
        "avg_rating": float(avg_rating) if avg_rating else None,
        "reviews_count": reviews_count,
        "photo_url": photo_url,
        "website": website,
        "favorite_books": parse_profile_favorite_books(html_text, limit),
        "currently_reading": parse_profile_currently_reading(html_text, limit),
        "shelves": parse_profile_shelves(html_text, parse_int(user_id) or 0, limit),
    }


def parse_author_books(author_id: str, limit: int) -> list[dict[str, Any]]:
    html_text = fetch_html(f"{BASE_URL}/author/list/{author_id}")
    books = []
    pattern = re.compile(
        r'<tr itemscope itemtype="http://schema.org/Book">.*?'
        r'<a title="(?P<title_attr>[^"]+)" href="(?P<book_href>/book/show/[^"]+)">.*?'
        r'<a class="authorName" itemprop="url" href="https://www.goodreads.com/author/show/(?P<author_id>\d+)\.[^"]+"><span itemprop="name">(?P<author_name>.*?)</span></a>'
        r'.*?<span class="minirating">.*?(?P<average>[0-9.]+) avg rating.*?(?P<ratings>[\d,]+) ratings',
        re.S,
    )
    for match in pattern.finditer(html_text):
        title = clean_html_text(match.group("title_attr"))
        href = match.group("book_href")
        image = first_match(rf'{re.escape(href)}">\s*<img[^>]+src="([^"]+)"', html_text)
        books.append(
            {
                "book_id": parse_int(first_match(r"/book/show/([0-9]+)", href)),
                "title": title,
                "cover_url": image,
                "web_url": absolute_url(href),
                "primary_author": clean_html_text(match.group("author_name")),
                "primary_author_id": parse_int(match.group("author_id")),
                "average_rating": float(match.group("average")),
                "ratings_count": parse_int(match.group("ratings")),
            }
        )
        if len(books) >= limit:
            break
    return unique_by(books, "book_id")


def get_public_author(author_id: str, limit: int) -> dict[str, Any]:
    html_text = fetch_html(f"{BASE_URL}/author/show/{author_id}")
    author_list_html = fetch_html(f"{BASE_URL}/author/list/{author_id}")
    name = clean_html_text(first_match(r'<h1[^>]*>\s*(?:<span itemprop="name">)?(.*?)(?:</span>)?\s*</h1>', html_text))
    bio = clean_html_text(first_match(rf'<span id="freeTextContainerauthor{author_id}">(.*?)</span>', html_text))
    location = clean_html_text(first_match(r'<div class="dataTitle">Born</div>\s*(.*?)\s*<br class="clear"/>', html_text))
    website = first_match(r'<div class="dataTitle">Website</div>\s*<div class="dataItem">\s*<a[^>]+href="([^"]+)"', html_text)
    twitter = clean_html_text(first_match(r'<div class="dataTitle">Twitter</div>\s*<div class="dataItem">\s*<a[^>]*>(.*?)</a>', html_text))
    member_since = clean_html_text(first_match(r'<div class="dataTitle">Member Since</div>\s*<div class="dataItem">(.*?)</div>', html_text))
    followers_count = parse_int(first_match(r"Followers \(([\d,]+)\)", html_text))
    average_rating = first_match(r"Average rating ([0-9.]+)", author_list_html) or first_match(
        r"Average rating:\s*([0-9.]+)",
        html_text,
    )
    works_count = parse_int(first_match(r"([\d,]+)\s+distinct works", html_text))
    photo_url = first_match(rf'<img[^>]+alt="{re.escape(name or "")}"[^>]+src="([^"]+)"', html_text) if name else None

    return {
        "author_id": parse_int(author_id),
        "name": name,
        "bio": bio,
        "location": location,
        "photo_url": photo_url,
        "average_rating": float(average_rating) if average_rating else None,
        "works_count": works_count,
        "website": website,
        "twitter": twitter,
        "member_since": member_since,
        "followers_count": followers_count,
        "books": parse_author_books(author_id, limit),
    }


def emit_json(value: Any) -> None:
    if isinstance(value, dict) and "__result__" in value:
        value = value["__result__"]
    print(json.dumps(value, ensure_ascii=False))


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(
            "Usage: public_graph.py <command> [args...]\n"
            "Commands: discover_runtime, get_public_book, list_book_reviews,\n"
            "  list_similar_books, list_series_books, search_books,\n"
            "  get_public_profile, get_public_author, list_author_books"
        )

    mode = sys.argv[1]
    if mode == "discover_runtime":
        page_url = sys.argv[2] if len(sys.argv) > 2 else None
        runtime, _was_cached = discover_runtime(page_url=page_url)
        emit_json(runtime)
        return

    if mode == "search_books":
        if len(sys.argv) not in {3, 4}:
            raise SystemExit("Usage: public_graph.py search_books <query> [limit]")
        query = sys.argv[2]
        limit = int(sys.argv[3]) if len(sys.argv) == 4 else 10
        emit_json(search_books(query, limit))
        return

    if mode in {"get_public_book", "list_book_reviews", "list_similar_books", "list_series_books"}:
        if len(sys.argv) not in {3, 4}:
            raise SystemExit(f"Usage: public_graph.py {mode} <book_id> [limit]")
        book_id = sys.argv[2]
        limit = int(sys.argv[3]) if len(sys.argv) == 4 else 10
        if mode == "get_public_book":
            emit_json(get_public_book(book_id))
            return
        if mode == "list_book_reviews":
            emit_json(list_book_reviews(book_id, limit))
            return
        if mode == "list_series_books":
            emit_json(list_series_books(book_id, limit))
            return
        emit_json(list_similar_books(book_id, limit))
        return

    if mode in {"get_public_profile", "get_public_author", "list_author_books"}:
        if len(sys.argv) not in {3, 4}:
            raise SystemExit(f"Usage: public_graph.py {mode} <id> [limit]")
        entity_id = sys.argv[2]
        limit = int(sys.argv[3]) if len(sys.argv) == 4 else 10
        if mode == "get_public_profile":
            emit_json(get_public_profile(entity_id, limit))
            return
        if mode == "get_public_author":
            emit_json(get_public_author(entity_id, limit))
            return
        emit_json(parse_author_books(entity_id, limit))
        return

    raise SystemExit(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
