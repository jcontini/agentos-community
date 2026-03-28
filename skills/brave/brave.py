"""Brave Search — privacy-focused web search with independent index."""

from agentos import surf

API_BASE = "https://api.search.brave.com/res/v1"


def search(*, query: str, limit: int = 20, freshness: str = None, **params) -> list[dict]:
    """Search the web using Brave's independent index."""
    api_key = params.get("auth", {}).get("key", "")
    q_params: dict = {"q": query, "count": limit}
    if freshness:
        q_params["freshness"] = freshness

    with surf(profile="api") as client:
        resp = client.get(
            f"{API_BASE}/web/search",
            params=q_params,
            headers={
                "X-Subscription-Token": api_key,
                "Accept": "application/json",
            },
        )
        resp.raise_for_status()

    results = resp.json().get("web", {}).get("results", [])
    return [
        {
            "id": r.get("url"),
            "name": r.get("title"),
            "text": r.get("description"),
            "url": r.get("url"),
            "image": (r.get("meta_url") or {}).get("favicon"),
            "indexed_at": r.get("page_age"),
        }
        for r in results
    ]
