"""Brave Search — privacy-focused web search with independent index."""

from agentos import http, connection, provides, returns, web_search

API_BASE = "https://api.search.brave.com/res/v1"


@returns("result[]")
@provides(web_search)
@connection("api")
def search(*, query: str, limit: int = 20, freshness: str = None, **params) -> list[dict]:
    """Search the web using Brave's independent index."""
    api_key = params.get("auth", {}).get("key", "")
    q_params: dict = {"q": query, "count": limit}
    if freshness:
        q_params["freshness"] = freshness

    resp = http.get(
        f"{API_BASE}/web/search",
        params=q_params,
        **http.headers(accept="json", extra={
            "X-Subscription-Token": api_key,
        }),
    )

    results = (resp["json"] or {}).get("web", {}).get("results", [])
    return [
        {
            "id": r.get("url"),
            "name": r.get("title"),
            "content": r.get("description"),
            "url": r.get("url"),
            "image": (r.get("meta_url") or {}).get("favicon"),
            "indexedAt": r.get("page_age"),
        }
        for r in results
    ]
