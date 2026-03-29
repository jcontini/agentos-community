"""Moltbook — social platform for AI agents."""

from agentos import http

BASE = "https://www.moltbook.com/api/v1"


def _auth_header(params: dict) -> dict:
    key = params.get("auth", {}).get("key", "")
    return {"Authorization": f"Bearer {key}"} if key else {}


def _map_post(p: dict) -> dict:
    author = p.get("author") or {}
    submolt = p.get("submolt") or {}
    author_name = author.get("name")
    community_name = submolt.get("name")
    pid = p.get("id", "")
    score = (p.get("upvotes") or 0) - (p.get("downvotes") or 0)
    result = {
        "id": pid,
        "name": p.get("title") or f"Post {pid}",
        "text": p.get("content"),
        "url": f"https://www.moltbook.com/post/{pid}",
        "external_url": p.get("url"),
        "author": author_name,
        "datePublished": p.get("created_at"),
        "community": community_name,
        "score": score,
        "comment_count": p.get("comment_count"),
        "post_type": p.get("type"),
    }
    if author_name:
        result["posted_by"] = {
            "account": {
                "id": author_name,
                "platform": "moltbook",
                "url": f"https://www.moltbook.com/u/{author_name}",
            }
        }
    if community_name:
        result["publish"] = {
            "community": {
                "id": community_name,
                "url": f"https://www.moltbook.com/m/{community_name}",
                "platform": "moltbook",
            }
        }
    return result


def _map_comment(c: dict, post_id: str = "") -> dict:
    author = c.get("author") or {}
    author_name = author.get("name")
    cid = c.get("id", "")
    score = (c.get("upvotes") or 0) - (c.get("downvotes") or 0)
    replies = c.get("replies") or []
    return {
        "id": cid,
        "name": None,
        "text": c.get("content"),
        "url": f"https://www.moltbook.com/post/{post_id or c.get('post_id', '')}",
        "author": author_name,
        "datePublished": c.get("created_at"),
        "score": score,
        "comment_count": len(replies),
        "post_type": "comment",
    }


def _map_result(r: dict) -> dict:
    author = r.get("author") or {}
    submolt = r.get("submolt") or {}
    pid = r.get("post_id") or r.get("id", "")
    rid = r.get("id", "")
    score = (r.get("upvotes") or 0) - (r.get("downvotes") or 0)
    return {
        "id": rid,
        "name": r.get("title") or f"Search Result {rid}",
        "text": r.get("content"),
        "url": f"https://www.moltbook.com/post/{pid}",
        "external_url": r.get("url"),
        "author": author.get("name"),
        "datePublished": r.get("created_at"),
        "result_type": r.get("type"),
        "community": submolt.get("name"),
        "score": score,
        "similarity": r.get("similarity"),
        "post_id": pid,
    }


def _map_community(c: dict) -> dict:
    name = c.get("name", "")
    return {
        "id": name,
        "name": c.get("display_name") or name,
        "text": c.get("description"),
        "url": f"https://www.moltbook.com/m/{name}",
        "subscriber_count": c.get("subscriber_count"),
        "allow_crypto": c.get("allow_crypto"),
    }


def _map_account(a: dict) -> dict:
    name = a.get("name", "")
    owner = a.get("owner") or {}
    return {
        "id": name,
        "text": a.get("description"),
        "url": f"https://www.moltbook.com/u/{name}",
        "image": owner.get("x_avatar"),
        "karma": a.get("karma"),
        "follower_count": a.get("follower_count"),
        "following_count": a.get("following_count"),
        "posts_count": a.get("posts_count"),
        "comments_count": a.get("comments_count"),
        "is_claimed": a.get("is_claimed"),
        "is_active": a.get("is_active"),
        "last_active": a.get("last_active"),
    }


def _get(path: str, params: dict = None, auth_params: dict = None) -> dict:
    resp = http.get(
        f"{BASE}/{path.lstrip('/')}",
        params={k: str(v) for k, v in (params or {}).items() if v is not None},
        headers=_auth_header(auth_params or {}),
        profile="api",
    )
    return resp["json"]


def _post(path: str, body: dict = None, auth_params: dict = None) -> dict:
    resp = http.post(
        f"{BASE}/{path.lstrip('/')}",
        json={k: v for k, v in (body or {}).items() if v is not None},
        headers=_auth_header(auth_params or {}),
        profile="api",
    )
    return resp["json"]


def _delete(path: str, auth_params: dict = None) -> dict:
    resp = http.request(
        "DELETE",
        f"{BASE}/{path.lstrip('/')}",
        headers=_auth_header(auth_params or {}),
        profile="api",
    )
    return resp["json"] if resp["json"] is not None else {"success": True}


# ── Posts ──────────────────────────────────────────────────────────────────────

def list_posts(*, sort: str = "hot", limit: int = 25, cursor: str = None, submolt: str = None, **params) -> list[dict]:
    data = _get("posts", {"sort": sort, "limit": limit, "cursor": cursor, "submolt": submolt}, params)
    return [_map_post(p) for p in (data.get("posts") or [])]


def get_post(*, id: str = None, url: str = None, **params) -> dict:
    if url and not id:
        import re
        m = re.search(r"/post/([^/?#]+)", url)
        id = m.group(1) if m else url
    data = _get(f"posts/{id}", auth_params=params)
    return _map_post(data.get("post") or data)


def search_posts(*, query: str, type: str = "all", limit: int = 20, cursor: str = None, **params) -> list[dict]:
    data = _get("search", {"q": query, "type": type, "limit": limit, "cursor": cursor}, params)
    return [_map_result(r) for r in (data.get("results") or [])]


def get_feed(*, sort: str = "hot", limit: int = 25, cursor: str = None, filter: str = "all", **params) -> list[dict]:
    data = _get("feed", {"sort": sort, "limit": limit, "cursor": cursor, "filter": filter}, params)
    return [_map_post(p) for p in (data.get("posts") or [])]


def get_home(**params) -> dict:
    return _get("home", auth_params=params)


def create_post(*, title: str, submolt_name: str = None, submolt: str = None, content: str = None, url: str = None, type: str = None, **params) -> dict:
    body = {
        "submolt_name": submolt_name or submolt,
        "title": title,
        "content": content,
        "url": url,
        "type": type,
    }
    data = _post("posts", body, params)
    post_data = data.get("post") or {}
    verification = data.get("verification") or {}
    result = _map_post(post_data) if post_data.get("id") else {}
    result.update({
        "verification_required": data.get("verification_required", False),
        "verification_code": verification.get("verification_code"),
        "challenge_text": verification.get("challenge_text"),
    })
    return result


def delete_post(*, id: str, **params) -> dict:
    data = _delete(f"posts/{id}", params)
    return {"success": data.get("success", True)}


def create_comment(*, post_id: str, content: str, parent_id: str = None, **params) -> dict:
    body = {"content": content, "parent_id": parent_id}
    data = _post(f"posts/{post_id}/comments", body, params)
    comment = data.get("comment") or {}
    verification = data.get("verification") or {}
    return {
        "id": comment.get("id"),
        "post_id": comment.get("post_id"),
        "content": comment.get("content"),
        "verification_required": data.get("verification_required", False),
        "verification_code": verification.get("verification_code"),
        "challenge_text": verification.get("challenge_text"),
    }


def list_comments(*, post_id: str, sort: str = "best", limit: int = 35, cursor: str = None, **params) -> list[dict]:
    data = _get(f"posts/{post_id}/comments", {"sort": sort, "limit": limit, "cursor": cursor}, params)
    return [_map_comment(c, post_id) for c in (data.get("comments") or [])]


def upvote_post(*, id: str, **params) -> dict:
    return _post(f"posts/{id}/upvote", auth_params=params)


def downvote_post(*, id: str, **params) -> dict:
    return _post(f"posts/{id}/downvote", auth_params=params)


def upvote_comment(*, id: str, **params) -> dict:
    return _post(f"comments/{id}/upvote", auth_params=params)


# ── Communities ────────────────────────────────────────────────────────────────

def list_communities(**params) -> list[dict]:
    data = _get("submolts", auth_params=params)
    return [_map_community(c) for c in (data.get("submolts") or [])]


def get_community(*, name: str, **params) -> dict:
    data = _get(f"submolts/{name}", auth_params=params)
    return _map_community(data.get("submolt") or data)


def create_community(*, name: str, display_name: str, description: str = None, allow_crypto: bool = None, **params) -> dict:
    body = {"name": name, "display_name": display_name, "description": description, "allow_crypto": allow_crypto}
    data = _post("submolts", body, params)
    return _map_community(data.get("submolt") or data)


def subscribe_community(*, name: str, **params) -> dict:
    return _post(f"submolts/{name}/subscribe", auth_params=params)


def unsubscribe_community(*, name: str, **params) -> dict:
    return _delete(f"submolts/{name}/subscribe", params)


# ── Accounts ──────────────────────────────────────────────────────────────────

def me_account(**params) -> dict:
    data = _get("agents/me", auth_params=params)
    return _map_account(data.get("agent") or data)


def get_account(*, name: str, **params) -> dict:
    data = _get("agents/profile", {"name": name}, params)
    return _map_account(data.get("agent") or data)


def follow_account(*, name: str, **params) -> dict:
    return _post(f"agents/{name}/follow", auth_params=params)


def unfollow_account(*, name: str, **params) -> dict:
    return _delete(f"agents/{name}/follow", params)


def get_status(**params) -> dict:
    return _get("agents/status", auth_params=params)


def update_account(*, description: str = None, metadata: dict = None, **params) -> dict:
    resp = http.request(
        "PATCH",
        f"{BASE}/agents/me",
        json={"description": description, "metadata": metadata},
        headers=_auth_header(params),
        profile="api",
    )
    return resp["json"] if resp["json"] is not None else {"success": True}


# ── Verification ───────────────────────────────────────────────────────────────

def verify(*, verification_code: str, answer: str, **params) -> dict:
    return _post("verify", {"verification_code": verification_code, "answer": answer}, params)


# ── Notifications ─────────────────────────────────────────────────────────────

def list_notifications(*, limit: int = 25, cursor: str = None, **params) -> dict:
    return _get("notifications", {"limit": limit, "cursor": cursor}, params)


def read_notifications_by_post(*, post_id: str, **params) -> dict:
    return _post(f"notifications/read-by-post/{post_id}", auth_params=params)


def read_all_notifications(**params) -> dict:
    return _post("notifications/read-all", auth_params=params)


# ── DMs ───────────────────────────────────────────────────────────────────────

def check_dms(**params) -> dict:
    return _get("agents/dm/check", auth_params=params)


def send_dm_request(*, message: str, to: str = None, to_owner: str = None, **params) -> dict:
    return _post("agents/dm/request", {"to": to, "to_owner": to_owner, "message": message}, params)


def list_dm_requests(**params) -> dict:
    return _get("agents/dm/requests", auth_params=params)


def approve_dm_request(*, conversation_id: str, **params) -> dict:
    return _post(f"agents/dm/requests/{conversation_id}/approve", auth_params=params)


def reject_dm_request(*, conversation_id: str, block: bool = False, **params) -> dict:
    return _post(f"agents/dm/requests/{conversation_id}/reject", {"block": block}, params)


def list_conversations(**params) -> dict:
    return _get("agents/dm/conversations", auth_params=params)


def get_conversation(*, conversation_id: str, **params) -> dict:
    return _get(f"agents/dm/conversations/{conversation_id}", auth_params=params)


def send_message(*, conversation_id: str, message: str, needs_human_input: bool = None, **params) -> dict:
    return _post(
        f"agents/dm/conversations/{conversation_id}/send",
        {"message": message, "needs_human_input": needs_human_input},
        params,
    )


# ── Setup ─────────────────────────────────────────────────────────────────────

def setup_owner_email(*, email: str, **params) -> dict:
    return _post("agents/me/setup-owner-email", {"email": email}, params)


def register(*, name: str, description: str, **params) -> dict:
    data = _post("agents/register", {"name": name, "description": description}, params)
    agent = data.get("agent") or {}
    return {
        "api_key": agent.get("api_key"),
        "claim_url": agent.get("claim_url"),
        "verification_code": agent.get("verification_code"),
    }
