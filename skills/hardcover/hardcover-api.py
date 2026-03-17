#!/usr/bin/env python3
import json
import sys
import urllib.error
import urllib.request


ENDPOINT = "https://api.hardcover.app/v1/graphql"
STATUS_TO_ID = {
    "want_to_read": 1,
    "reading": 2,
    "read": 3,
    "dnf": 5,
}
ID_TO_STATUS = {value: key for key, value in STATUS_TO_ID.items()}


def fail(message, code=1):
    print(json.dumps({"error": message}))
    sys.exit(code)


def read_payload():
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


def graphql(token, query, variables=None):
    if not token:
        fail("Missing Hardcover API token")
    body = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={
            "content-type": "application/json",
            "authorization": token,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        fail(f"Hardcover API error {exc.code}: {message}")
    except Exception as exc:
        fail(str(exc))
    if data.get("errors"):
        fail(data["errors"][0].get("message", "GraphQL request failed"))
    return data.get("data") or {}


def author_names(cached_contributors):
    authors = []
    for item in cached_contributors or []:
        author = (item or {}).get("author") or {}
        name = author.get("name")
        if name:
            authors.append(name)
    return authors


def normalize_book(book, *, user_book=None):
    authors = author_names(book.get("cached_contributors"))
    image = book.get("image") or {}
    normalized = {
        "id": str(book.get("id")),
        "book_id": str(book.get("id")),
        "title": book.get("title"),
        "authors": authors,
        "primary_author": authors[0] if authors else None,
        "description": book.get("description"),
        "page_count": book.get("pages"),
        "published_year": book.get("release_year"),
        "image": image.get("url"),
        "url": f"https://hardcover.app/books/{book.get('slug')}" if book.get("slug") else None,
        "users_count": book.get("users_count"),
        "ratings_count": book.get("ratings_count"),
        "rating": book.get("rating"),
        "status": None,
        "review": None,
        "user_book_id": None,
    }
    if user_book:
        normalized["status"] = ID_TO_STATUS.get(user_book.get("status_id"))
        normalized["review"] = user_book.get("review_raw")
        normalized["user_book_id"] = str(user_book.get("id")) if user_book.get("id") is not None else None
        if user_book.get("rating") not in (None, 0):
            normalized["rating"] = user_book.get("rating")
    return normalized


def search_books(token, query_text, limit):
    search_data = graphql(
        token,
        """
        query SearchBooks($query: String!, $limit: Int!) {
          search(query: $query, query_type: "Book", per_page: $limit, page: 1, sort: "activities_count:desc") {
            ids
          }
        }
        """,
        {"query": query_text, "limit": limit},
    )
    ids = ((search_data.get("search") or {}).get("ids")) or []
    if not ids:
        print("[]")
        return
    books_data = graphql(
        token,
        """
        query GetBooks($ids: [Int!]!) {
          books(where: {id: {_in: $ids}}, order_by: {users_count: desc}) {
            id
            title
            slug
            description
            pages
            release_year
            users_count
            ratings_count
            rating
            cached_contributors
            image { url }
          }
        }
        """,
        {"ids": ids},
    )
    books = books_data.get("books") or []
    print(json.dumps([normalize_book(book) for book in books]))


def list_library(token, limit):
    me = graphql(token, "query { me { id } }")
    me_list = me.get("me") or []
    if not me_list:
        fail("Unable to resolve authenticated Hardcover user")
    user_id = me_list[0]["id"]
    data = graphql(
        token,
        """
        query GetUserBooks($userId: Int!, $limit: Int!) {
          user_books(
            where: {user_id: {_eq: $userId}, status_id: {_neq: 6}}
            order_by: {date_added: desc}
            limit: $limit
          ) {
            id
            rating
            status_id
            review_raw
            book {
              id
              title
              slug
              description
              pages
              release_year
              image { url }
              cached_contributors
              users_count
              ratings_count
              rating
            }
          }
        }
        """,
        {"userId": user_id, "limit": limit},
    )
    user_books = data.get("user_books") or []
    print(json.dumps([normalize_book(item.get("book") or {}, user_book=item) for item in user_books]))


def get_book(token, book_id):
    data = graphql(
        token,
        """
        query GetBook($id: Int!) {
          books_by_pk(id: $id) {
            id
            title
            slug
            description
            pages
            release_year
            users_count
            ratings_count
            rating
            cached_contributors
            image { url }
          }
        }
        """,
        {"id": int(book_id)},
    )
    book = data.get("books_by_pk")
    if not book:
        fail(f"Book {book_id} not found")
    print(json.dumps(normalize_book(book)))


def add_book(token, book_id, status):
    status_id = STATUS_TO_ID.get(status or "want_to_read")
    if status_id is None:
        fail("status must be one of want_to_read, reading, read, dnf")
    data = graphql(
        token,
        """
        mutation AddBook($bookId: Int!, $statusId: Int!) {
          insert_user_book(object: {book_id: $bookId, status_id: $statusId}) {
            id
          }
        }
        """,
        {"bookId": int(book_id), "statusId": status_id},
    )
    row = data.get("insert_user_book") or {}
    print(json.dumps({"ok": True, "user_book_id": str(row.get("id")), "status": ID_TO_STATUS[status_id]}))


def update_book(token, user_book_id, status=None, rating=None):
    status_id = STATUS_TO_ID.get(status) if status else None
    if status and status_id is None:
        fail("status must be one of want_to_read, reading, read, dnf")
    variables = {"id": int(user_book_id), "statusId": status_id, "rating": rating}
    data = graphql(
        token,
        """
        mutation UpdateUserBook($id: Int!, $statusId: Int, $rating: numeric) {
          update_user_book(
            pk_columns: {id: $id}
            _set: {status_id: $statusId, rating: $rating}
          ) {
            id
            status_id
            rating
          }
        }
        """,
        variables,
    )
    row = data.get("update_user_book") or {}
    print(
        json.dumps(
            {
                "ok": True,
                "user_book_id": str(row.get("id")),
                "status": ID_TO_STATUS.get(row.get("status_id")),
                "rating": row.get("rating"),
            }
        )
    )


def delete_book(token, user_book_id):
    data = graphql(
        token,
        """
        mutation DeleteUserBook($id: Int!) {
          delete_user_book(id: $id) {
            id
          }
        }
        """,
        {"id": int(user_book_id)},
    )
    row = data.get("delete_user_book") or {}
    print(json.dumps({"ok": True, "user_book_id": str(row.get("id"))}))


def main():
    if len(sys.argv) < 2:
        fail("Missing operation")
    operation = sys.argv[1]
    payload = read_payload()
    params = payload.get("params") or {}
    auth = payload.get("auth") or {}
    token = auth.get("key")

    if operation == "search":
        query_text = params.get("query")
        if not query_text:
            fail("Missing query")
        search_books(token, query_text, int(params.get("limit", 5)))
        return
    if operation == "list":
        list_library(token, int(params.get("limit", 100)))
        return
    if operation == "get":
        get_book(token, params.get("book_id"))
        return
    if operation == "add":
        add_book(token, params.get("book_id"), params.get("status"))
        return
    if operation == "update":
        update_book(token, params.get("user_book_id"), params.get("status"), params.get("rating"))
        return
    if operation == "delete":
        delete_book(token, params.get("user_book_id"))
        return
    fail(f"Unknown operation: {operation}")


if __name__ == "__main__":
    main()
