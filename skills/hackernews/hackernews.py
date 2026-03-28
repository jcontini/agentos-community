"""Hacker News — public Algolia API, no auth required."""

from agentos import surf

BASE = "https://hn.algolia.com/api/v1"
SITE = "https://news.ycombinator.com"


def _post_url(object_id: str) -> str:
    return f"{SITE}/item?id={object_id}"


def _user_url(username: str) -> str:
    return f"{SITE}/user?id={username}"


def _map_hit(hit: dict) -> dict:
    """Map an Algolia search hit to shape-native post fields."""
    oid = hit.get("objectID", "")
    author = hit.get("author", "")
    return {
        "id": oid,
        "name": hit.get("title"),
        "text": hit.get("text"),
        "url": _post_url(oid),
        "external_url": hit.get("url"),
        "author": author,
        "datePublished": hit.get("created_at"),
        "score": hit.get("points"),
        "comment_count": hit.get("num_comments"),
        "posted_by": {
            "id": author,
            "name": author,
            "url": _user_url(author),
        } if author else None,
    }


def _map_item(item: dict) -> dict:
    """Map an Algolia items API response to shape-native post fields."""
    item_id = str(item.get("id", ""))
    author = item.get("author", "")
    children = item.get("children", [])

    def map_comment(c: dict) -> dict:
        cid = str(c.get("id", ""))
        cauthor = c.get("author", "")
        return {
            "id": cid,
            "text": c.get("text"),
            "url": _post_url(cid),
            "author": cauthor,
            "datePublished": c.get("created_at"),
            "posted_by": {
                "id": cauthor,
                "name": cauthor,
                "url": _user_url(cauthor),
            } if cauthor else None,
            "replies": [map_comment(child) for child in c.get("children", [])],
        }

    return {
        "id": item_id,
        "name": item.get("title"),
        "text": item.get("text"),
        "url": _post_url(item_id),
        "external_url": item.get("url"),
        "author": author,
        "datePublished": item.get("created_at"),
        "score": item.get("points"),
        "comment_count": len(children),
        "posted_by": {
            "id": author,
            "name": author,
            "url": _user_url(author),
        } if author else None,
        "replies": [map_comment(c) for c in children],
    }


def list_posts(feed: str = "front", limit: int = 30) -> list[dict]:
    endpoint = "search_by_date" if feed == "new" else "search"
    tag_map = {"new": "story", "ask": "ask_hn", "show": "show_hn"}
    tags = tag_map.get(feed, "front_page")

    with surf() as client:
        resp = client.get(f"{BASE}/{endpoint}", params={
            "tags": tags,
            "hitsPerPage": limit,
        })
        resp.raise_for_status()

    return [_map_hit(h) for h in resp.json().get("hits", [])]


def search_posts(query: str, limit: int = 30) -> list[dict]:
    with surf() as client:
        resp = client.get(f"{BASE}/search", params={
            "query": query,
            "tags": "story",
            "hitsPerPage": limit,
        })
        resp.raise_for_status()

    return [_map_hit(h) for h in resp.json().get("hits", [])]


def get_post(id: str = None, url: str = None) -> dict:
    if url and not id:
        import re
        m = re.search(r"[?&]id=(\d+)", url)
        if m:
            id = m.group(1)
    if not id:
        from agentos import skill_error
        return skill_error("Either id or url with id= parameter is required")

    with surf() as client:
        resp = client.get(f"{BASE}/items/{id}")
        resp.raise_for_status()

    return _map_item(resp.json())


def comments_post(id: str) -> list[dict]:
    """Flatten comment tree into a list with replies_to relations."""
    with surf() as client:
        resp = client.get(f"{BASE}/items/{id}")
        resp.raise_for_status()

    item = resp.json()
    result = []

    def flatten(node: dict, parent_id: str | None):
        nid = str(node.get("id", ""))
        author = node.get("author", "")
        post = {
            "id": nid,
            "name": node.get("title"),
            "text": node.get("text"),
            "url": _post_url(nid),
            "external_url": node.get("url"),
            "author": author,
            "datePublished": node.get("created_at"),
            "score": node.get("points"),
            "comment_count": len(node.get("children", [])),
            "posted_by": {
                "id": author,
                "name": author,
                "url": _user_url(author),
            } if author else None,
        }
        if parent_id:
            post["replies_to"] = {"id": parent_id}
        result.append(post)
        for child in node.get("children", []):
            flatten(child, nid)

    flatten(item, None)
    return result
