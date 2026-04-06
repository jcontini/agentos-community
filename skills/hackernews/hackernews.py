"""Hacker News — public Algolia API, no auth required."""

from agentos import http, provides, returns, web_read, web_search

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
        "content": hit.get("text"),
        "url": _post_url(oid),
        "externalUrl": hit.get("url"),
        "author": author,
        "published": hit.get("created_at"),
        "score": hit.get("points"),
        "commentCount": hit.get("num_comments"),
        "postedBy": {
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
            "content": c.get("text"),
            "url": _post_url(cid),
            "author": cauthor,
            "published": c.get("created_at"),
            "postedBy": {
                "id": cauthor,
                "name": cauthor,
                "url": _user_url(cauthor),
            } if cauthor else None,
            "replies": [map_comment(child) for child in c.get("children", [])],
        }

    return {
        "id": item_id,
        "name": item.get("title"),
        "content": item.get("text"),
        "url": _post_url(item_id),
        "externalUrl": item.get("url"),
        "author": author,
        "published": item.get("created_at"),
        "score": item.get("points"),
        "commentCount": len(children),
        "postedBy": {
            "id": author,
            "name": author,
            "url": _user_url(author),
        } if author else None,
        "replies": [map_comment(c) for c in children],
    }


@returns("post[]")
def list_posts(feed: str = "front", limit: int = 30, **params) -> list[dict]:
    """List Hacker News stories by feed type

        Args:
            feed: Feed type: front, new, ask, show
            limit: Number of stories (max 100)
        """
    endpoint = "search_by_date" if feed == "new" else "search"
    tag_map = {"new": "story", "ask": "ask_hn", "show": "show_hn"}
    tags = tag_map.get(feed, "front_page")

    resp = http.get(f"{BASE}/{endpoint}", params={
        "tags": tags,
        "hitsPerPage": str(limit),
    })

    return [_map_hit(h) for h in (resp["json"] or {}).get("hits", [])]


@returns("post[]")
@provides(web_search)
def search_posts(query: str, limit: int = 30, **params) -> list[dict]:
    """Search Hacker News stories

        Args:
            query: Search query
            limit: Number of results (max 100)
        """
    resp = http.get(f"{BASE}/search", params={
        "query": query,
        "tags": "story",
        "hitsPerPage": str(limit),
    })

    return [_map_hit(h) for h in (resp["json"] or {}).get("hits", [])]


@returns("post")
@provides(web_read, urls=["news.ycombinator.com/item*"])
def get_post(id: str = None, url: str = None, **params) -> dict:
    """Get a Hacker News story with comments

        Args:
            id: Story ID (optional if url is a news.ycombinator.com item link)
            url: HN item URL with id= in the query (web_read)
        """
    if url and not id:
        import re
        m = re.search(r"[?&]id=(\d+)", url)
        if m:
            id = m.group(1)
    if not id:
        from agentos import skill_error
        return skill_error("Either id or url with id= parameter is required")

    resp = http.get(f"{BASE}/items/{id}")

    return _map_item(resp["json"])


@returns("post[]")
def comments_post(id: str, **params) -> list[dict]:
    """Flatten comment tree into a list with replies_to relations."""
    resp = http.get(f"{BASE}/items/{id}")

    item = resp["json"]
    result = []

    def flatten(node: dict, parent_id: str | None):
        nid = str(node.get("id", ""))
        author = node.get("author", "")
        post = {
            "id": nid,
            "name": node.get("title"),
            "content": node.get("text"),
            "url": _post_url(nid),
            "externalUrl": node.get("url"),
            "author": author,
            "published": node.get("created_at"),
            "score": node.get("points"),
            "commentCount": len(node.get("children", [])),
            "postedBy": {
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
