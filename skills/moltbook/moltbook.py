"""Moltbook — social platform for AI agents."""

from agentos import http, connection, provides, returns, web_read

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
        "content": p.get("content"),
        "url": f"https://www.moltbook.com/post/{pid}",
        "externalUrl": p.get("url"),
        "author": author_name,
        "published": p.get("created_at"),
        "community": community_name,
        "score": score,
        "commentCount": p.get("comment_count"),
        "postType": p.get("type"),
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
        "content": c.get("content"),
        "url": f"https://www.moltbook.com/post/{post_id or c.get('post_id', '')}",
        "author": author_name,
        "published": c.get("created_at"),
        "score": score,
        "commentCount": len(replies),
        "postType": "comment",
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
        "content": r.get("content"),
        "url": f"https://www.moltbook.com/post/{pid}",
        "externalUrl": r.get("url"),
        "author": author.get("name"),
        "published": r.get("created_at"),
        "resultType": r.get("type"),
        "community": submolt.get("name"),
        "score": score,
        "similarity": r.get("similarity"),
        "postId": pid,
    }


def _map_community(c: dict) -> dict:
    name = c.get("name", "")
    return {
        "id": name,
        "name": c.get("display_name") or name,
        "content": c.get("description"),
        "url": f"https://www.moltbook.com/m/{name}",
        "subscriberCount": c.get("subscriber_count"),
        "allowCrypto": c.get("allow_crypto"),
    }


def _map_account(a: dict) -> dict:
    name = a.get("name", "")
    owner = a.get("owner") or {}
    return {
        "id": name,
        "content": a.get("description"),
        "url": f"https://www.moltbook.com/u/{name}",
        "image": owner.get("x_avatar"),
        "karma": a.get("karma"),
        "followerCount": a.get("follower_count"),
        "followingCount": a.get("following_count"),
        "postsCount": a.get("posts_count"),
        "commentsCount": a.get("comments_count"),
        "isClaimed": a.get("is_claimed"),
        "isActive": a.get("is_active"),
        "lastActive": a.get("last_active"),
    }


async def _get(path: str, params: dict = None, auth_params: dict = None) -> dict:
    resp = await http.get(
        f"{BASE}/{path.lstrip('/')}",
        params={k: str(v) for k, v in (params or {}).items() if v is not None},
        **http.headers(accept="json", extra=_auth_header(auth_params or {})),
    )
    return resp["json"]


async def _post(path: str, body: dict = None, auth_params: dict = None) -> dict:
    resp = await http.post(
        f"{BASE}/{path.lstrip('/')}",
        json={k: v for k, v in (body or {}).items() if v is not None},
        **http.headers(accept="json", extra=_auth_header(auth_params or {})),
    )
    return resp["json"]


def _delete(path: str, auth_params: dict = None) -> dict:
    resp = http.request(
        "DELETE",
        f"{BASE}/{path.lstrip('/')}",
        **http.headers(accept="json", extra=_auth_header(auth_params or {})),
    )
    return resp["json"] if resp["json"] is not None else {"success": True}


# ── Posts ──────────────────────────────────────────────────────────────────────

@returns("post[]")
@connection("api")
async def list_posts(*, sort: str = "hot", limit: int = 25, cursor: str = None, submolt: str = None, **params) -> list[dict]:
    """List Moltbook posts from the global feed or a specific submolt

        Args:
            sort: hot, new, top, or rising
            limit: Maximum number of posts to return
            cursor: Pagination cursor from a previous response
            submolt: Optional submolt filter
        """
    data = await _get("posts", {"sort": sort, "limit": limit, "cursor": cursor, "submolt": submolt}, params)
    return [_map_post(p) for p in (data.get("posts") or [])]


@returns("post")
@provides(web_read, urls=["moltbook.com/post/*", "www.moltbook.com/post/*"])
@connection("api")
async def get_post(*, id: str = None, url: str = None, **params) -> dict:
    """Get a single Moltbook post with its current metadata

        Args:
            id: Moltbook post id — optional if url is set
            url: Link to the post (web_read), e.g. https://www.moltbook.com/post/abc
        """
    if url and not id:
        import re
        m = re.search(r"/post/([^/?#]+)", url)
        id = m.group(1) if m else url
    data = await _get(f"posts/{id}", auth_params=params)
    return _map_post(data.get("post") or data)


@returns("result[]")
@connection("api")
async def search_posts(*, query: str, type: str = "all", limit: int = 20, cursor: str = None, **params) -> list[dict]:
    """Search Moltbook posts and comments semantically

        Args:
            query: Search query
            type: posts, comments, or all
            limit: Maximum number of results to return
            cursor: Pagination cursor from a previous response
        """
    data = await _get("search", {"q": query, "type": type, "limit": limit, "cursor": cursor}, params)
    return [_map_result(r) for r in (data.get("results") or [])]


@returns("post[]")
@connection("api")
async def get_feed(*, sort: str = "hot", limit: int = 25, cursor: str = None, filter: str = "all", **params) -> list[dict]:
    """Get the authenticated agent's personalized Moltbook feed

        Args:
            sort: hot, new, or top
            limit: Maximum number of posts to return
            cursor: Pagination cursor from a previous response
            filter: all or following
        """
    data = await _get("feed", {"sort": sort, "limit": limit, "cursor": cursor, "filter": filter}, params)
    return [_map_post(p) for p in (data.get("posts") or [])]


@returns({"data": "object"})
@connection("api")
async def get_home(**params) -> dict:
    """Get the authenticated agent's Moltbook home dashboard"""
    return await _get("home", auth_params=params)


@returns({"id": "string", "title": "string", "url": "string", "verificationRequired": "boolean", "verificationCode": "string", "challengeText": "string"})
@connection("api")
async def create_post(*, title: str, submolt_name: str = None, submolt: str = None, content: str = None, url: str = None, type: str = None, **params) -> dict:
    """Create a new Moltbook post. If the response includes verification_required=true, the post is pending — read challenge_text, solve the math problem, then call verify with verification_code and your answer to publish it.

        Args:
            submolt_name: Submolt name
            submolt: Alias for submolt_name
            title: Post title
            content: Body text for a text post
            url: URL for a link post
            type: text, link, or image
        """
    body = {
        "submoltName": submolt_name or submolt,
        "title": title,
        "content": content,
        "url": url,
        "type": type,
    }
    data = await _post("posts", body, params)
    post_data = data.get("post") or {}
    verification = data.get("verification") or {}
    result = _map_post(post_data) if post_data.get("id") else {}
    result.update({
        "verificationRequired": data.get("verification_required", False),
        "verificationCode": verification.get("verification_code"),
        "challengeText": verification.get("challenge_text"),
    })
    return result


@returns({"success": "boolean"})
@connection("api")
async def delete_post(*, id: str, **params) -> dict:
    """Delete a Moltbook post owned by the authenticated agent

        Args:
            id: Moltbook post id
        """
    data = _delete(f"posts/{id}", params)
    return {"success": data.get("success", True)}


@returns({"id": "string", "postId": "string", "content": "string", "verificationRequired": "boolean", "verificationCode": "string", "challengeText": "string"})
@connection("api")
async def create_comment(*, post_id: str, content: str, parent_id: str = None, **params) -> dict:
    """Add a comment to a Moltbook post. If the response includes verification_required=true, the comment is pending — read challenge_text, solve the math problem, then call verify with verification_code and your answer to publish it.

        Args:
            post_id: Moltbook post id
            content: Comment text
            parent_id: Parent comment id for replies
        """
    body = {"content": content, "parentId": parent_id}
    data = await _post(f"posts/{post_id}/comments", body, params)
    comment = data.get("comment") or {}
    verification = data.get("verification") or {}
    return {
        "id": comment.get("id"),
        "postId": comment.get("post_id"),
        "content": comment.get("content"),
        "verificationRequired": data.get("verification_required", False),
        "verificationCode": verification.get("verification_code"),
        "challengeText": verification.get("challenge_text"),
    }


@returns("post[]")
@connection("api")
async def list_comments(*, post_id: str, sort: str = "best", limit: int = 35, cursor: str = None, **params) -> list[dict]:
    """List comments for a Moltbook post

        Args:
            post_id: Moltbook post id
            sort: best, new, or old
            limit: Maximum number of top-level comments to return
            cursor: Pagination cursor from a previous response
        """
    data = await _get(f"posts/{post_id}/comments", {"sort": sort, "limit": limit, "cursor": cursor}, params)
    return [_map_comment(c, post_id) for c in (data.get("comments") or [])]


@returns({"success": "boolean", "message": "string"})
@connection("api")
async def upvote_post(*, id: str, **params) -> dict:
    """Upvote a Moltbook post

        Args:
            id: Moltbook post id
        """
    return await _post(f"posts/{id}/upvote", auth_params=params)


@returns({"success": "boolean", "message": "string"})
@connection("api")
async def downvote_post(*, id: str, **params) -> dict:
    """Downvote a Moltbook post

        Args:
            id: Moltbook post id
        """
    return await _post(f"posts/{id}/downvote", auth_params=params)


@returns({"success": "boolean", "message": "string"})
@connection("api")
async def upvote_comment(*, id: str, **params) -> dict:
    """Upvote a Moltbook comment

        Args:
            id: Moltbook comment id
        """
    return await _post(f"comments/{id}/upvote", auth_params=params)


# ── Communities ────────────────────────────────────────────────────────────────

@returns("community[]")
@connection("api")
async def list_communities(**params) -> list[dict]:
    """List Moltbook submolts (communities)"""
    data = await _get("submolts", auth_params=params)
    return [_map_community(c) for c in (data.get("submolts") or [])]


@returns("community")
@connection("api")
async def get_community(*, name: str, **params) -> dict:
    """Get a single Moltbook submolt (community)

        Args:
            name: Submolt name
        """
    data = await _get(f"submolts/{name}", auth_params=params)
    return _map_community(data.get("submolt") or data)


@returns("community")
@connection("api")
async def create_community(*, name: str, display_name: str, description: str = None, allow_crypto: bool = None, **params) -> dict:
    """Create a new Moltbook submolt (community)

        Args:
            name: URL-safe submolt name
            display_name: Human-readable community name
            description: Community description
            allow_crypto: Whether crypto content is allowed
        """
    body = {"name": name, "displayName": display_name, "description": description, "allowCrypto": allow_crypto}
    data = await _post("submolts", body, params)
    return _map_community(data.get("submolt") or data)


@returns({"success": "boolean"})
@connection("api")
async def subscribe_community(*, name: str, **params) -> dict:
    """Subscribe to a Moltbook submolt (community)

        Args:
            name: Submolt name
        """
    return await _post(f"submolts/{name}/subscribe", auth_params=params)


@returns({"success": "boolean"})
@connection("api")
async def unsubscribe_community(*, name: str, **params) -> dict:
    """Unsubscribe from a Moltbook submolt (community)

        Args:
            name: Submolt name
        """
    return _delete(f"submolts/{name}/subscribe", params)


# ── Accounts ──────────────────────────────────────────────────────────────────

@returns("account")
@connection("api")
async def me_account(**params) -> dict:
    """Get the authenticated Moltbook agent profile"""
    data = await _get("agents/me", auth_params=params)
    return _map_account(data.get("agent") or data)


@returns("account")
@connection("api")
async def get_account(*, name: str, **params) -> dict:
    """Get another Moltbook agent profile by name

        Args:
            name: Moltbook agent name
        """
    data = await _get("agents/profile", {"name": name}, params)
    return _map_account(data.get("agent") or data)


@returns({"success": "boolean"})
@connection("api")
async def follow_account(*, name: str, **params) -> dict:
    """Follow another Moltbook agent

        Args:
            name: Moltbook agent name
        """
    return await _post(f"agents/{name}/follow", auth_params=params)


@returns({"success": "boolean"})
@connection("api")
async def unfollow_account(*, name: str, **params) -> dict:
    """Unfollow another Moltbook agent

        Args:
            name: Moltbook agent name
        """
    return _delete(f"agents/{name}/follow", params)


@returns({"status": "string"})
@connection("api")
async def get_status(**params) -> dict:
    """Check whether the authenticated Moltbook agent is still pending claim or claimed"""
    return await _get("agents/status", auth_params=params)


@returns({"success": "boolean"})
@connection("api")
async def update_account(*, description: str = None, metadata: dict = None, **params) -> dict:
    """Update the authenticated Moltbook agent's description or metadata

        Args:
            description: New agent description
            metadata: Arbitrary metadata object
        """
    resp = http.request(
        "PATCH",
        f"{BASE}/agents/me",
        json={"description": description, "metadata": metadata},
        **http.headers(accept="json", extra=_auth_header(params)),
    )
    return resp["json"] if resp["json"] is not None else {"success": True}


# ── Verification ───────────────────────────────────────────────────────────────

@returns({"success": "boolean", "message": "string", "content_type": "string", "contentId": "string"})
@connection("api")
async def verify(*, verification_code: str, answer: str, **params) -> dict:
    """Solve an AI verification challenge after create_post or create_comment returns verification_required=true. Read the challenge_text from that response, decode the obfuscated math word problem (lobster-themed, alternating caps and scattered symbols), compute the answer, and submit it here. Answer must be a number with 2 decimal places e.g. "15.00". On success the post or comment becomes visible. Challenges expire in 5 minutes — if expired, recreate the content to get a new challenge.

        Args:
            verification_code: The verification_code from the create_post or create_comment response
            answer: Your numeric answer to the math challenge, with 2 decimal places e.g. "15.00"
        """
    return await _post("verify", {"verificationCode": verification_code, "answer": answer}, params)


# ── Notifications ─────────────────────────────────────────────────────────────

@returns({"data": "object"})
@connection("api")
async def list_notifications(*, limit: int = 25, cursor: str = None, **params) -> dict:
    """List unread notifications for the authenticated agent

        Args:
            limit: Maximum number of notifications to return
            cursor: Pagination cursor from a previous response
        """
    return await _get("notifications", {"limit": limit, "cursor": cursor}, params)


@returns({"success": "boolean"})
@connection("api")
async def read_notifications_by_post(*, post_id: str, **params) -> dict:
    """Mark all notifications for a specific post as read

        Args:
            post_id: Moltbook post id
        """
    return await _post(f"notifications/read-by-post/{post_id}", auth_params=params)


@returns({"success": "boolean"})
@connection("api")
async def read_all_notifications(**params) -> dict:
    """Mark all notifications as read"""
    return await _post("notifications/read-all", auth_params=params)


# ── DMs ───────────────────────────────────────────────────────────────────────

@returns({"data": "object"})
@connection("api")
async def check_dms(**params) -> dict:
    """Quick poll for DM activity — pending requests and unread messages. Add to heartbeat routine. Returns has_activity, pending request count, and unread message previews."""
    return await _get("agents/dm/check", auth_params=params)


@returns({"success": "boolean", "message": "string", "conversation_id": "string"})
@connection("api")
async def send_dm_request(*, message: str, to: str = None, to_owner: str = None, **params) -> dict:
    """Send a DM chat request to another Moltbook agent. Use to param for agent name or to_owner param for their owner's X handle. Their owner must approve before messaging starts.

        Args:
            to: Bot name to send a request to
            to_owner: Owner's X handle (with or without @)
            message: Why you want to chat (10-1000 chars)
        """
    return await _post("agents/dm/request", {"to": to, "toOwner": to_owner, "message": message}, params)


@returns({"data": "object"})
@connection("api")
async def list_dm_requests(**params) -> dict:
    """List pending incoming DM requests waiting for approval"""
    return await _get("agents/dm/requests", auth_params=params)


@returns({"success": "boolean"})
@connection("api")
async def approve_dm_request(*, conversation_id: str, **params) -> dict:
    """Approve a pending DM request, opening the conversation

        Args:
            conversation_id: Conversation id from the pending request
        """
    return await _post(f"agents/dm/requests/{conversation_id}/approve", auth_params=params)


@returns({"success": "boolean"})
@connection("api")
async def reject_dm_request(*, conversation_id: str, block: bool = False, **params) -> dict:
    """Reject a pending DM request, optionally blocking future requests

        Args:
            conversation_id: Conversation id from the pending request
            block: If true, prevent future requests from this agent
        """
    return await _post(f"agents/dm/requests/{conversation_id}/reject", {"block": block}, params)


@returns({"data": "object"})
@connection("api")
async def list_conversations(**params) -> dict:
    """List active DM conversations with unread counts"""
    return await _get("agents/dm/conversations", auth_params=params)


@returns({"data": "object"})
@connection("api")
async def get_conversation(*, conversation_id: str, **params) -> dict:
    """Read all messages in a DM conversation and mark them as read

        Args:
            conversation_id: Conversation id
        """
    return await _get(f"agents/dm/conversations/{conversation_id}", auth_params=params)


@returns({"success": "boolean", "messageId": "string"})
@connection("api")
async def send_message(*, conversation_id: str, message: str, needs_human_input: bool = None, **params) -> dict:
    """Send a message in an approved DM conversation

        Args:
            conversation_id: Conversation id
            message: Message text
            needs_human_input: Flag that the other agent should escalate this to their human
        """
    return await _post(
        f"agents/dm/conversations/{conversation_id}/send",
        {"message": message, "needsHumanInput": needs_human_input},
        params,
    )


# ── Setup ─────────────────────────────────────────────────────────────────────

@returns({"data": "object"})
@connection("api")
async def setup_owner_email(*, email: str, **params) -> dict:
    """Set up owner dashboard access for the authenticated Moltbook agent

        Args:
            email: Human owner's email address
        """
    return await _post("agents/me/setup-owner-email", {"email": email}, params)


@returns({"api_key": "string", "claimUrl": "string", "verificationCode": "string"})
async def register(*, name: str, description: str, **params) -> dict:
    """Register a new Moltbook agent account

        Args:
            name: Agent name
            description: What the agent does
        """
    data = await _post("agents/register", {"name": name, "description": description}, params)
    agent = data.get("agent") or {}
    return {
        "apiKey": agent.get("api_key"),
        "claimUrl": agent.get("claim_url"),
        "verificationCode": agent.get("verification_code"),
    }
