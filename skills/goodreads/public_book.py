#!/usr/bin/env python3

import json
import re
import sys
import time
import urllib.request
from urllib.error import HTTPError, URLError
from datetime import datetime, timezone


USER_AGENT = "Mozilla/5.0 (compatible; AgentOS/1.0)"
GRAPHQL_ENDPOINT = "https://kxbwmqov6jgg3daaamb744ycu4.appsync-api.us-east-1.amazonaws.com/graphql"
GRAPHQL_API_KEY = "da2-xpgsdydkbregjhpr6ejzqdhuwy"


def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    last_error = None
    for attempt in range(4):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read().decode("utf-8", errors="replace")
        except HTTPError as error:
            last_error = error
            if error.code not in {429, 500, 502, 503, 504} or attempt == 3:
                raise
        except URLError as error:
            last_error = error
            if attempt == 3:
                raise
        time.sleep(1.5 * (attempt + 1))

    raise RuntimeError(f"Failed to fetch Goodreads page: {last_error}")


def graphql_request(query: str, variables: dict) -> dict:
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
        "x-api-key": GRAPHQL_API_KEY,
    }

    last_error = None
    for attempt in range(4):
        request = urllib.request.Request(
            GRAPHQL_ENDPOINT,
            data=payload,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8", errors="replace"))
                errors = body.get("errors") or []
                if errors:
                    messages = "; ".join(
                        error.get("message", "Unknown GraphQL error") for error in errors
                    )
                    raise RuntimeError(messages)
                return body.get("data") or {}
        except HTTPError as error:
            last_error = error
            if error.code not in {429, 500, 502, 503, 504} or attempt == 3:
                raise
        except URLError as error:
            last_error = error
            if attempt == 3:
                raise
        time.sleep(1.5 * (attempt + 1))

    raise RuntimeError(f"Failed Goodreads GraphQL request: {last_error}")


def extract_next_data(html: str) -> dict:
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.S,
    )
    if not match:
        raise RuntimeError("Could not find __NEXT_DATA__ on Goodreads book page")
    return json.loads(match.group(1))


def load_book_page(book_id: str):
    html = fetch_html(f"https://www.goodreads.com/book/show/{book_id}")
    next_data = extract_next_data(html)
    page_props = next_data.get("props", {}).get("pageProps", {})
    apollo = page_props.get("apolloState", {})
    root_query = apollo.get("ROOT_QUERY", {})

    book_ref = root_query.get(f'getBookByLegacyId({{"legacyId":"{book_id}"}})', {}).get(
        "__ref"
    )
    if not book_ref or book_ref not in apollo:
        raise RuntimeError(f"Could not resolve public book data for Goodreads book {book_id}")

    book = apollo[book_ref]
    work = deref(apollo, book.get("work"))
    work_details = deref(work, work.get("details") if work else None)
    work_stats = deref(work, work.get("stats") if work else None)

    return html, next_data, page_props, apollo, root_query, book, work, work_details, work_stats


def deref(apollo: dict, value):
    if isinstance(apollo, dict) and isinstance(value, dict) and "__ref" in value:
        return apollo.get(value["__ref"])
    return value


def parse_review_id(review: dict) -> str:
    review_url = (((review.get("shelving") or {}).get("webUrl")) or "")
    match = re.search(r"/review/show/([0-9]+)", review_url)
    if match:
        return match.group(1)
    return review.get("id")


def iso_from_ms(value):
    if not isinstance(value, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()
    except (ValueError, OSError):
        return None


def emit_book(book_id: str) -> None:
    _, _, _, apollo, root_query, book, _, work_details, work_stats = load_book_page(book_id)

    details = book.get("details") or {}
    primary_edge = book.get("primaryContributorEdge") or {}
    primary_contributor = deref(apollo, (primary_edge.get("node") or {}))

    contributors = []
    for edge in [primary_edge, *(book.get("secondaryContributorEdges") or [])]:
        contributor = deref(apollo, (edge.get("node") or {}))
        if not contributor:
            continue
        contributors.append(
            {
                "role": edge.get("role"),
                "author_id": contributor.get("legacyId"),
                "name": contributor.get("name"),
                "url": contributor.get("webUrl"),
                "image_url": contributor.get("profileImageUrl"),
            }
        )

    genres = []
    genre_urls = []
    for item in book.get("bookGenres") or []:
        genre = item.get("genre") or {}
        name = genre.get("name")
        url = genre.get("webUrl")
        if name:
            genres.append(name)
        if url:
            genre_urls.append(url)

    series = []
    for item in book.get("bookSeries") or []:
        series_name = ((item.get("series") or {}).get("title")) or item.get("title")
        if series_name:
            series.append(series_name)

    social_signals = root_query.get(
        f'getSocialSignals({{"bookId":"{book.get("id")}","shelfStatus":["CURRENTLY_READING","TO_READ"]}})',
        [],
    )
    social_counts = {}
    for signal in social_signals or []:
        name = signal.get("name")
        count = signal.get("count")
        if name and count is not None:
            social_counts[name] = count

    places = [item.get("name") for item in (work_details or {}).get("places") or [] if item.get("name")]
    characters = [
        item.get("name")
        for item in (work_details or {}).get("characters") or []
        if item.get("name")
    ]
    awards = [
        item.get("name")
        for item in (work_details or {}).get("awardsWon") or []
        if isinstance(item, dict) and item.get("name")
    ]

    payload = {
        "book_id": book.get("legacyId") or int(book_id),
        "title": book.get("title"),
        "description": book.get('description({"stripped":true})') or book.get("description"),
        "cover_url": book.get("imageUrl"),
        "primary_author": (primary_contributor or {}).get("name"),
        "primary_author_id": (primary_contributor or {}).get("legacyId"),
        "primary_author_url": (primary_contributor or {}).get("webUrl"),
        "isbn": details.get("isbn"),
        "isbn13": details.get("isbn13"),
        "publication_date": iso_from_ms(details.get("publicationTime") or (work_details or {}).get("publicationTime")),
        "average_rating": (work_stats or {}).get("averageRating"),
        "ratings_count": (work_stats or {}).get("ratingsCount"),
        "review_count": (work_stats or {}).get("textReviewsCount"),
        "pages": details.get("numPages"),
        "genres": genres,
        "genre_urls": genre_urls,
        "series_name": series[0] if series else None,
        "series": series,
        "publisher": details.get("publisher"),
        "format": details.get("format"),
        "language": ((details.get("language") or {}).get("name")),
        "web_url": book.get("webUrl"),
        "work_url": (work_details or {}).get("webUrl"),
        "original_title": (work_details or {}).get("originalTitle"),
        "currently_reading_count": social_counts.get("CURRENTLY_READING"),
        "to_read_count": social_counts.get("TO_READ"),
        "contributors": contributors,
        "places": places,
        "characters": characters,
        "awards_won": awards,
    }
    print(json.dumps(payload, ensure_ascii=False))


def map_review_list(apollo: dict, edges, book):
    reviews = []
    for edge in edges:
        review = deref(apollo, (edge.get("node") or {}))
        if not review:
            continue

        creator = deref(apollo, review.get("creator")) or {}
        shelving = review.get("shelving") or {}
        shelf = shelving.get("shelf") or {}
        taggings = shelving.get("taggings") or []
        tags = [((tagging.get("tag") or {}).get("name")) for tagging in taggings if (tagging.get("tag") or {}).get("name")]

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


def emit_reviews(book_id: str, limit: int) -> None:
    _, _, _, apollo, _, book, work, _, _ = load_book_page(book_id)
    query = """
fragment SocialUserFragment on User {
  followersCount
}

fragment ReviewerProfileFragment on User {
  id: legacyId
  imageUrlSquare
  isAuthor
  ...SocialUserFragment
  textReviewsCount
  name
  webUrl
  contributor {
    id
    works {
      totalCount
    }
  }
}

fragment ReviewCardFragment on Review {
  __typename
  id
  creator {
    ...ReviewerProfileFragment
  }
  recommendFor
  updatedAt
  createdAt
  spoilerStatus
  lastRevisionAt
  text
  rating
  preReleaseBookSource
  shelving {
    shelf {
      name
      displayName
      editable
      default
      actionType
      sortOrder
      webUrl
    }
    taggings {
      tag {
        name
        webUrl
      }
    }
    webUrl
  }
  likeCount
  commentCount
}

fragment BookReviewsFragment on BookReviewsConnection {
  totalCount
  edges {
    node {
      ...ReviewCardFragment
    }
  }
  pageInfo {
    prevPageToken
    nextPageToken
  }
}

query getReviews($filters: BookReviewsFilterInput!, $pagination: PaginationInput) {
  getReviews(filters: $filters, pagination: $pagination) {
    ...BookReviewsFragment
  }
}
""".strip()

    work_id = (work or {}).get("id")
    if work_id:
        data = graphql_request(
            query,
            {
                "filters": {"resourceType": "WORK", "resourceId": work_id},
                "pagination": {"limit": limit},
            },
        )
        edges = (((data.get("getReviews") or {}).get("edges")) or [])
    else:
        edges = (((apollo.get("ROOT_QUERY") or {}).get("getReviews")) or {}).get("edges") or []

    print(json.dumps(map_review_list(apollo, edges, book), ensure_ascii=False))


def emit_similar_books(book_id: str, limit: int) -> None:
    _, _, _, _, _, book, _, _, _ = load_book_page(book_id)
    query = """
query getSimilarBooks($id: ID!, $limit: Int!) {
  getSimilarBooks(id: $id, pagination: { limit: $limit }) {
    webUrl
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

    data = graphql_request(query, {"id": book.get("id"), "limit": limit})
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

    print(json.dumps(books, ensure_ascii=False))


def main() -> None:
    if len(sys.argv) not in {3, 4}:
        raise SystemExit(
            "Usage: public_book.py <get_book|list_book_reviews|list_similar_books> <book_id> [limit]"
        )

    mode = sys.argv[1]
    book_id = sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) == 4 else 20

    if mode == "get_book":
        emit_book(book_id)
        return
    if mode == "list_book_reviews":
        emit_reviews(book_id, limit)
        return
    if mode == "list_similar_books":
        emit_similar_books(book_id, limit)
        return

    raise SystemExit(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
