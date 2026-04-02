"""Firefox skill — browsing history, bookmarks, and cookies via SQLite.

Firefox stores everything in plaintext SQLite databases (no decryption needed).
Two databases: places.sqlite (history + bookmarks) and cookies.sqlite (cookies).

All public functions accept **kw for forward-compatibility with engine context.
"""

from agentos import sql

PLACES_DB = "~/Library/Application Support/Firefox/Profiles/*/places.sqlite"
COOKIES_DB = "~/Library/Application Support/Firefox/Profiles/*/cookies.sqlite"


def _db(connection, default):
    """Resolve database path from connection context or fall back to default."""
    if connection and isinstance(connection, dict):
        return connection.get("sqlite", default)
    return default


# ==============================================================================
# History operations
# ==============================================================================


def _map_webpage(row):
    """Map a SQL row to the webpage shape."""
    return {
        "id": row["url"],
        "name": row.get("title") or row["url"],
        "url": row["url"],
        "visit_count": row.get("visit_count"),
        "last_visit_unix": row.get("last_visit_unix"),
    }


def op_list_webpages(*, limit=200, connection=None, **kw):
    """List recently visited pages from Firefox browsing history."""
    rows = sql.query("""
        SELECT p.url, p.title, p.visit_count,
               CAST(p.last_visit_date / 1000000 AS INTEGER) AS last_visit_unix
        FROM moz_places p
        WHERE p.hidden = 0
          AND p.visit_count > 0
          AND p.url NOT LIKE 'place:%'
        ORDER BY p.last_visit_date DESC
        LIMIT :limit
    """, db=_db(connection, PLACES_DB), params={"limit": limit})
    return [_map_webpage(r) for r in rows]


def op_search_webpages(*, query, limit=200, connection=None, **kw):
    """Search Firefox browsing history by URL or title."""
    rows = sql.query("""
        SELECT p.url, p.title, p.visit_count,
               CAST(p.last_visit_date / 1000000 AS INTEGER) AS last_visit_unix
        FROM moz_places p
        WHERE p.hidden = 0
          AND p.visit_count > 0
          AND p.url NOT LIKE 'place:%'
          AND (p.url LIKE :query OR p.title LIKE :query)
        ORDER BY p.last_visit_date DESC
        LIMIT :limit
    """, db=_db(connection, PLACES_DB), params={
        "query": f"%{query}%",
        "limit": limit,
    })
    return [_map_webpage(r) for r in rows]


# ==============================================================================
# Bookmarks
# ==============================================================================


def op_list_bookmarks(*, limit=200, connection=None, **kw):
    """List Firefox bookmarks (excluding folders and separators)."""
    return sql.query("""
        SELECT b.title AS bookmark_title, p.url, p.title,
               CAST(b.dateAdded / 1000000 AS INTEGER) AS date_added_unix
        FROM moz_bookmarks b
        JOIN moz_places p ON b.fk = p.id
        WHERE b.type = 1
          AND p.url NOT LIKE 'place:%'
        ORDER BY b.dateAdded DESC
        LIMIT :limit
    """, db=_db(connection, PLACES_DB), params={"limit": limit})


# ==============================================================================
# Cookies
# ==============================================================================


def op_list_cookies(*, domain, limit=200, connection=None, **kw):
    """List cookies for a domain from Firefox (plaintext, no decryption needed)."""
    return sql.query("""
        SELECT name, value, host, path, expiry,
               isSecure AS is_secure, isHttpOnly AS is_httponly,
               (creationTime / 1000000) AS created
        FROM moz_cookies
        WHERE host LIKE :domain
        ORDER BY name
        LIMIT :limit
    """, db=_db(connection, COOKIES_DB), params={
        "domain": f"%{domain}%",
        "limit": limit,
    })


def op_cookie_get(*, domain, names=None, limit=200, connection=None, **kw):
    """Extract cookies for a domain — provider interface for cookie matchmaking.

    Returns { domain, cookies, count, source } for the runtime to consume.
    """
    cookies = sql.query("""
        SELECT name, value, host, path, expiry,
               isSecure AS is_secure, isHttpOnly AS is_httponly,
               (creationTime / 1000000) AS created
        FROM moz_cookies
        WHERE host LIKE :domain
          AND (:names = '' OR instr(',' || :names || ',', ',' || name || ',') > 0)
        ORDER BY name
        LIMIT :limit
    """, db=_db(connection, COOKIES_DB), params={
        "domain": f"%{domain}%",
        "names": names or "",
        "limit": limit,
    })

    return {
        "domain": domain,
        "cookies": cookies,
        "count": len(cookies),
        "source": "firefox",
    }
