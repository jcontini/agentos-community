#!/usr/bin/env python3

import html
import json
import re
import sys
import time
from typing import Any

from agentos import http, shell, molt, clean_html, parse_int, iso_from_ms


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
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    return fetch_url(url, headers=headers)


def fetch_url(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    data: str | None = None,
    method: str | None = None,
) -> str:
    last_error = None
    request_method = method or ("POST" if data is not None else "GET")
    dispatch = {"GET": http.get, "POST": http.post, "PUT": http.put, "DELETE": http.delete}
    fn = dispatch.get(request_method, http.get)

    for attempt in range(4):
        kwargs = {"headers": headers or {}, "profile": "navigate", "timeout": 30}
        if data is not None:
            kwargs["data"] = data
        try:
            resp = fn(url, **kwargs)
            if resp.get("ok"):
                return resp.get("body", "")
            status = resp.get("status", 0)
            last_error = RuntimeError(f"HTTP {status}")
            if status not in {429, 500, 502, 503, 504} or attempt == 3:
                raise last_error
        except RuntimeError:
            if attempt == 3:
                raise
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed Goodreads request: {last_error}")




def absolute_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return f"{BASE_URL}{url}"




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
            headers={"Accept": "*/*"},
        )
    except Exception:
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
        result = shell.run("node", ["-e", script, page_url], timeout=90)
    except Exception:
        return None

    if result["exit_code"] != 0 or not result["stdout"].strip():
        return None

    try:
        captured = json.loads(result["stdout"])
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
    payload = json.dumps({"query": query, "variables": variables})
    body = fetch_url(
        runtime["graphql_endpoint"],
        headers=headers,
        data=payload,
        method="POST",
    )
    parsed = json.loads(body)
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

    author_id = primary_contributor.get("legacyId")
    author_name = primary_contributor.get("name")
    author_url = primary_contributor.get("webUrl")

    # Shape-native contributor dicts (author shape)
    shaped_contributors = []
    for c in unique_by(contributors, "name"):
        shaped_contributors.append({
            "id": c.get("author_id") or c.get("name"),
            "name": c.get("name"),
            "url": c.get("url"),
            "image": c.get("image_url"),
            "role": c.get("role"),
        })

    result = {
        "id": book.get("legacyId"),
        "name": book.get("title"),
        "text": book.get('description({"stripped":true})') or book.get("description"),
        "url": book.get("webUrl") or (f"https://goodreads.com/book/show/{book.get('legacyId')}" if book.get("legacyId") else None),
        "image": book.get("imageUrl"),
        "author": author_name,
        "isbn": details.get("isbn"),
        "isbn13": details.get("isbn13"),
        "datePublished": iso_from_ms(details.get("publicationTime") or work_details.get("publicationTime")),
        "average_rating": work_stats.get("averageRating"),
        "ratings_count": work_stats.get("ratingsCount"),
        "review_count": work_stats.get("textReviewsCount"),
        "pages": details.get("numPages"),
        "genres": genres,
        "series": series[0] if series else None,
        "publisher": {"id": details.get("publisher"), "name": details.get("publisher")} if details.get("publisher") else None,
        "format": details.get("format"),
        "language": ((details.get("language") or {}).get("name")),
        "work_url": work_details.get("webUrl"),
        "original_title": work_details.get("originalTitle"),
        "currently_reading_count": social_counts.get("CURRENTLY_READING"),
        "to_read_count": social_counts.get("TO_READ"),
    }
    if author_id or author_name:
        result["written_by"] = {
            "id": author_id or author_name,
            "name": author_name,
            "url": author_url,
        }
    if shaped_contributors:
        result["contributors"] = shaped_contributors
    return result


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
        review_id = parse_review_id(review)
        book_id = book.get("legacyId")
        book_title = book.get("title")
        reviewer_id = creator.get("legacyId") or creator.get("id")
        reviewer_name = creator.get("name")

        entry: dict[str, Any] = {
            "id": review_id,
            "name": f"Review of {book_title}" if book_title else "Review",
            "text": review.get("text"),
            "url": shelving.get("webUrl") or (f"https://goodreads.com/review/show/{review_id}" if review_id else None),
            "author": reviewer_name,
            "datePublished": iso_from_ms(review.get("createdAt")),
            "engagement": {
                "rating": review.get("rating"),
                "likes": review.get("likeCount"),
            },
            "comment_count": review.get("commentCount"),
            "tags": tags,
            "shelf_name": shelf.get("name"),
        }
        if reviewer_id or reviewer_name:
            entry["posted_by"] = {
                "id": reviewer_id,
                "name": reviewer_name,
                "url": creator.get("webUrl") or (f"https://goodreads.com/user/show/{reviewer_id}" if reviewer_id else None),
                "image": creator.get("imageUrlSquare"),
                "followers_count": creator.get("followersCount"),
                "reviews_count": creator.get("textReviewsCount"),
            }
        if book_id or book_title:
            entry["references"] = {
                "id": book_id,
                "name": book_title,
                "url": f"https://goodreads.com/book/show/{book_id}" if book_id else None,
                "image": book.get("imageUrl"),
                "author": book.get("primaryContributorEdge", {}).get("node", {}).get("name") if isinstance(book.get("primaryContributorEdge"), dict) else None,
            }
        reviews.append(entry)
    return reviews


def _simple_book(book_id: Any, title: str | None, cover_url: str | None,
                  web_url: str | None, author: str | None,
                  author_id: Any = None, avg_rating: Any = None,
                  ratings_count: Any = None, **extra: Any) -> dict[str, Any]:
    """Build a minimal shape-native book dict."""
    result: dict[str, Any] = {
        "id": book_id,
        "name": title,
        "image": cover_url,
        "url": web_url or (f"https://goodreads.com/book/show/{book_id}" if book_id else None),
        "author": author,
    }
    if avg_rating is not None:
        result["average_rating"] = avg_rating
    if ratings_count is not None:
        result["ratings_count"] = ratings_count
    if author_id or author:
        result["written_by"] = {
            "id": author_id or author,
            "name": author,
        }
    result.update(extra)
    return result


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
        stats = (node.get("work") or {}).get("stats") or {}
        books.append(_simple_book(
            book_id=int(match.group(1)) if match else web_url,
            title=node.get("title"),
            cover_url=node.get("imageUrl"),
            web_url=web_url,
            author=(((node.get("primaryContributorEdge") or {}).get("node")) or {}).get("name"),
            avg_rating=stats.get("averageRating"),
            ratings_count=stats.get("ratingsCount"),
        ))
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
        books.append(_simple_book(
            book_id=int(match.group(1)) if match else None,
            title=node.get("title"),
            cover_url=node.get("imageUrl"),
            web_url=web_url,
            author=contributor.get("name"),
            author_id=contributor.get("legacyId"),
        ))
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
        books.append(_simple_book(
            book_id=best.get("legacyId"),
            title=best.get("title"),
            cover_url=best.get("imageUrl"),
            web_url=best.get("webUrl"),
            author=contributor.get("name"),
            author_id=contributor.get("legacyId"),
            avg_rating=stats.get("averageRating"),
            ratings_count=stats.get("ratingsCount"),
            series_placement=edge.get("seriesPlacement"),
            is_primary=edge.get("isPrimary"),
        ))
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
        title = molt(alt) or ""
        author = None
        if " by " in title:
            title, author = title.rsplit(" by ", 1)
        books.append(_simple_book(
            book_id=parse_int(first_match(r"/book/show/([0-9]+)", href)),
            title=title,
            cover_url=image,
            web_url=absolute_url(href),
            author=author,
        ))
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
        shelves.append({
            "id": f"{user_id}:{html.unescape(shelf_name)}",
            "name": molt(label),
            "book_count": parse_int(count),
            "url": absolute_url(href),
        })
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
        books.append(_simple_book(
            book_id=parse_int(first_match(r"/book/show/([0-9]+)", match.group("book_href"))),
            title=clean_html(match.group("title")),
            cover_url=match.group("cover"),
            web_url=absolute_url(match.group("book_href")),
            author=clean_html(match.group("author_name")),
            author_id=parse_int(first_match(r"/author/show/([0-9]+)", match.group("author_href"))),
        ))
        if len(books) >= limit:
            break
    return unique_by(books, "book_id")


def get_public_profile(user_id: str, limit: int) -> dict[str, Any]:
    html_text = fetch_html(f"{BASE_URL}/user/show/{user_id}")
    title = molt(first_match(r"<title>(.*?)</title>", html_text)) or ""
    title_match = re.match(r"^(.*?) \((.*?)\) - (.*?) \(([\d,]+) books\)$", title)
    name = clean_html(first_match(r'<h1 id="profileNameTopHeading"[^>]*>(.*?)</h1>', html_text))
    username = first_match(r'<meta property="profile:username" content="([^"]+)"', html_text)
    ratings_count = parse_int(first_match(r'>([\d,]+) ratings</a>', html_text))
    avg_rating = first_match(r"\(([\d.]+) avg\)", html_text)
    reviews_count = parse_int(
        first_match(r'view=reviews">\s*([\d,]+) reviews', html_text)
        or first_match(r"([\d,]+) reviews", html_text)
    )
    photo_url = first_match(r'<meta property="og:image" content="([^"]+)"', html_text)
    website = first_match(r'<a rel="me noopener noreferrer"[^>]*href="([^"]+)"', html_text)

    uid = parse_int(user_id)
    result: dict[str, Any] = {
        "id": uid,
        "name": name or (title_match.group(1) if title_match else None),
        "handle": username or (title_match.group(2) if title_match else None),
        "url": f"https://goodreads.com/user/show/{uid}" if uid else None,
        "image": photo_url,
        "location": title_match.group(3) if title_match else None,
        "books_count": parse_int(title_match.group(4) if title_match else None),
        "ratings_count": ratings_count,
        "avg_rating": float(avg_rating) if avg_rating else None,
        "reviews_count": reviews_count,
        "website": website,
    }
    favorite_books = parse_profile_favorite_books(html_text, limit)
    if favorite_books:
        result["favorite_books"] = favorite_books
    currently_reading = parse_profile_currently_reading(html_text, limit)
    if currently_reading:
        result["currently_reading"] = currently_reading
    shelves = parse_profile_shelves(html_text, uid or 0, limit)
    if shelves:
        result["shelves"] = shelves
    return result


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
        title = clean_html(match.group("title_attr"))
        href = match.group("book_href")
        image = first_match(rf'{re.escape(href)}">\s*<img[^>]+src="([^"]+)"', html_text)
        books.append(_simple_book(
            book_id=parse_int(first_match(r"/book/show/([0-9]+)", href)),
            title=title,
            cover_url=image,
            web_url=absolute_url(href),
            author=clean_html(match.group("author_name")),
            author_id=parse_int(match.group("author_id")),
            avg_rating=float(match.group("average")),
            ratings_count=parse_int(match.group("ratings")),
        ))
        if len(books) >= limit:
            break
    return unique_by(books, "book_id")


def get_public_author(author_id: str, limit: int) -> dict[str, Any]:
    html_text = fetch_html(f"{BASE_URL}/author/show/{author_id}")
    author_list_html = fetch_html(f"{BASE_URL}/author/list/{author_id}")
    name = clean_html(first_match(r'<h1[^>]*>\s*(?:<span itemprop="name">)?(.*?)(?:</span>)?\s*</h1>', html_text))
    bio = clean_html(first_match(rf'<span id="freeTextContainerauthor{author_id}">(.*?)</span>', html_text))
    location = clean_html(first_match(r'<div class="dataTitle">Born</div>\s*(.*?)\s*<br class="clear"/>', html_text))
    website = first_match(r'<div class="dataTitle">Website</div>\s*<div class="dataItem">\s*<a[^>]+href="([^"]+)"', html_text)
    twitter = clean_html(first_match(r'<div class="dataTitle">Twitter</div>\s*<div class="dataItem">\s*<a[^>]*>(.*?)</a>', html_text))
    member_since = clean_html(first_match(r'<div class="dataTitle">Member Since</div>\s*<div class="dataItem">(.*?)</div>', html_text))
    followers_count = parse_int(first_match(r"Followers \(([\d,]+)\)", html_text))
    average_rating = first_match(r"Average rating ([0-9.]+)", author_list_html) or first_match(
        r"Average rating:\s*([0-9.]+)",
        html_text,
    )
    works_count = parse_int(first_match(r"([\d,]+)\s+distinct works", html_text))
    photo_url = first_match(rf'<img[^>]+alt="{re.escape(name or "")}"[^>]+src="([^"]+)"', html_text) if name else None

    aid = parse_int(author_id)
    result: dict[str, Any] = {
        "id": aid,
        "name": name,
        "text": bio,
        "url": f"https://goodreads.com/author/show/{aid}" if aid else None,
        "image": photo_url,
        "location": location,
        "average_rating": float(average_rating) if average_rating else None,
        "works_count": works_count,
        "website": website,
        "twitter": twitter,
        "member_since": member_since,
        "followers_count": followers_count,
    }
    books = parse_author_books(author_id, limit)
    if books:
        result["books"] = books
    return result


# ---------------------------------------------------------------------------
# Entry points (called by AgentOS with params: true)
# ---------------------------------------------------------------------------


def _p(d: dict | None, key: str, default: Any = None) -> Any:
    """Get from params sub-dict or top-level."""
    if not d:
        return default
    p = d.get("params", d) if isinstance(d, dict) else {}
    return p.get(key, default) if isinstance(p, dict) else default


def _extract_id_from_url(params: dict | None, url_key: str, id_key: str, pattern: str) -> str | None:
    """Extract an ID from a URL param, falling back to the explicit ID param."""
    url = _p(params, url_key)
    if url:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return _p(params, id_key)


def run_get_profile(*, user_id: str = "", limit: int = 10, **params) -> dict[str, Any]:
    return get_public_profile(user_id=str(user_id), limit=int(limit))


def run_get_book(*, book_id: str = "", url: str = "", **params) -> dict[str, Any]:
    if url:
        m = re.search(r"/book/show/(\d+)", url)
        if m:
            book_id = m.group(1)
    return get_public_book(str(book_id))


def run_list_book_reviews(*, book_id: str = "", limit: int = 30, **params) -> Any:
    return list_book_reviews(book_id=str(book_id), limit=int(limit))


def run_list_similar_books(*, book_id: str = "", limit: int = 20, **params) -> Any:
    return list_similar_books(book_id=str(book_id), limit=int(limit))


def run_list_series_books(*, book_id: str = "", limit: int = 20, **params) -> Any:
    return list_series_books(book_id=str(book_id), limit=int(limit))


def run_search_books(*, query: str = "", limit: int = 10, **params) -> Any:
    return search_books(query=str(query), limit=int(limit))


def run_get_author(*, author_id: str = "", url: str = "", limit: int = 10, **params) -> dict[str, Any]:
    if url:
        m = re.search(r"/author/show/(\d+)", url)
        if m:
            author_id = m.group(1)
    return get_public_author(author_id=str(author_id), limit=int(limit))


def run_list_author_books(*, author_id: str = "", limit: int = 10, **params) -> list[dict[str, Any]]:
    return parse_author_books(author_id=str(author_id), limit=int(limit))


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
