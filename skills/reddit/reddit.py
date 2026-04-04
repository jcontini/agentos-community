"""Reddit — public JSON API, no auth required."""

import re
from datetime import datetime, timezone

from agentos import http

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AgentOS/1.0)",
    "Accept": "application/json",
}


def _ts(epoch: int | float | None) -> str | None:
    """Convert Unix timestamp to ISO 8601."""
    if epoch is None:
        return None
    return datetime.fromtimestamp(int(epoch), tz=timezone.utc).isoformat()


def _map_post(d: dict) -> dict:
    """Map a Reddit post/comment data dict to shape-native post fields."""
    author = d.get("author", "")
    subreddit = d.get("subreddit", "")
    return {
        "id": d.get("id"),
        "name": d.get("title"),
        "content": d.get("selftext") or d.get("body"),
        "url": f"https://reddit.com{d['permalink']}" if d.get("permalink") else None,
        "author": author,
        "published": _ts(d.get("created_utc")),
        "score": d.get("score"),
        "commentCount": d.get("num_comments"),
        "postedBy": {
            "id": author,
            "name": author,
            "url": f"https://reddit.com/u/{author}",
        } if author else None,
        "publish": {
            "id": subreddit,
            "name": subreddit,
            "url": f"https://reddit.com/r/{subreddit}",
        } if subreddit else None,
    }


def _map_community(d: dict) -> dict:
    """Map a subreddit data dict to shape-native community fields."""
    display = d.get("display_name", "")
    return {
        "id": d.get("name"),
        "name": display,
        "content": d.get("public_description"),
        "url": f"https://reddit.com/r/{display}" if display else None,
        "image": d.get("community_icon") or d.get("icon_img"),
        "subscriberCount": d.get("subscribers"),
        "privacy": "OPEN",
    }


def _get_json(path: str, params: dict | None = None) -> dict:
    resp = http.get(f"https://www.reddit.com{path}", headers=HEADERS, params=params)
    return resp["json"]


def search_posts(query: str, limit: int = 25, sort: str = "relevance") -> list[dict]:
    data = _get_json("/search.json", {"q": query, "limit": limit, "sort": sort})
    return [_map_post(c["data"]) for c in data.get("data", {}).get("children", [])]


def list_posts(subreddit: str, sort: str = "hot", limit: int = 25) -> list[dict]:
    data = _get_json(f"/r/{subreddit}/{sort}.json", {"limit": limit})
    return [_map_post(c["data"]) for c in data.get("data", {}).get("children", [])]


def get_post(id: str = None, url: str = None, comment_limit: int = None) -> dict:
    if url and not id:
        m = re.search(r"comments/([a-z0-9]+)", url)
        if m:
            id = m.group(1)
    if not id:
        from agentos import skill_error
        return skill_error("Either id or url is required")

    params = {}
    if comment_limit:
        params["limit"] = comment_limit

    data = _get_json(f"/comments/{id}.json", params)
    post_data = data[0]["data"]["children"][0]["data"]
    post = _map_post(post_data)

    # Build nested comment tree
    def map_comment(c: dict) -> dict:
        d = c["data"]
        author = d.get("author", "")
        replies_raw = d.get("replies")
        children = []
        if isinstance(replies_raw, dict):
            children = [
                map_comment(rc)
                for rc in replies_raw.get("data", {}).get("children", [])
                if rc.get("kind") == "t1"
            ]
        return {
            "id": d.get("id"),
            "content": d.get("body"),
            "author": author,
            "published": _ts(d.get("created_utc")),
            "score": d.get("ups"),
            "postedBy": {
                "id": author,
                "name": author,
                "url": f"https://reddit.com/u/{author}",
            } if author else None,
            "replies": children,
        }

    comments = [
        map_comment(c)
        for c in data[1]["data"]["children"]
        if c.get("kind") == "t1"
    ]
    post["replies"] = comments
    return post


def comments_post(id: str, comment_limit: int = None) -> list[dict]:
    """Flatten comment tree into a list with replies_to relations."""
    params = {}
    if comment_limit:
        params["limit"] = comment_limit

    data = _get_json(f"/comments/{id}.json", params)
    post_data = data[0]["data"]["children"][0]["data"]
    result = [_map_post(post_data)]

    def flatten(c: dict, parent_id: str):
        d = c["data"]
        author = d.get("author", "")
        comment = {
            "id": d.get("id"),
            "content": d.get("body"),
            "url": f"https://reddit.com{d['permalink']}" if d.get("permalink") else None,
            "author": author,
            "published": _ts(d.get("created_utc")),
            "score": d.get("ups"),
            "postedBy": {
                "id": author,
                "name": author,
                "url": f"https://reddit.com/u/{author}",
            } if author else None,
            "repliesTo": {"id": parent_id},
        }
        result.append(comment)
        replies_raw = d.get("replies")
        if isinstance(replies_raw, dict):
            for rc in replies_raw.get("data", {}).get("children", []):
                if rc.get("kind") == "t1":
                    flatten(rc, d.get("id"))

    for c in data[1]["data"]["children"]:
        if c.get("kind") == "t1":
            flatten(c, post_data.get("id"))

    return result


def get_community(subreddit: str) -> dict:
    data = _get_json(f"/r/{subreddit}/about.json")
    return _map_community(data.get("data", {}))


def search_communities(query: str, limit: int = 25) -> list[dict]:
    data = _get_json("/subreddits/search.json", {"q": query, "limit": limit})
    return [_map_community(c["data"]) for c in data.get("data", {}).get("children", [])]
