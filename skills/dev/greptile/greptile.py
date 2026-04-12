"""greptile.py — Dashboard session + org member management for Greptile.

Auth architecture
-----------------
Greptile's dashboard (app.greptile.com) uses **Auth.js v5** (the rebrand of
NextAuth). The session lives in `__Secure-authjs.session-token` — a JWE stored
as a single (un-chunked, ~1.2KB) cookie on the `app.greptile.com` host.

The dashboard session response ALSO contains a `greptileToken` — a short-lived
HS256 JWT that the browser passes as `Authorization: Bearer <token>` to the
**backend API** at a separate host (see _backend_base). That backend is where
org / people / invites actually live — the `/api/auth/session` route on
app.greptile.com is Auth.js only.

Transport note: Dashboard is Vercel-hosted and blocks HTTP/2 — use
`http.headers(waf="vercel")` which sets `http2=False`.

A subtle engine detail: passing the engine-resolved cookie header through
`http.client(cookies=...)` was observed to *not* round-trip correctly for
`__Host-`/`__Secure-` prefixed Auth.js cookies (session came back null even
though the cookies were fresh). Passing the same cookies as a raw
`Cookie:` header on each one-shot `http.get/post` works. All tools here use
the one-shot path.
"""

import json
import re

from agentos import http, connection, returns, timeout

DASHBOARD_BASE = "https://app.greptile.com"

# The actual backend API host. Express-powered, but org/people mutations go
# through the dashboard's tRPC route at /api/trpc instead — the backend is used
# by different features (code search, reviews, etc.).
BACKEND_BASE = "https://api.greptile.com"

# tRPC router lives at /api/trpc on the dashboard. Procedure names captured from
# bundle spelunking — see readme.md "People / Org API" table.
TRPC_BASE = f"{DASHBOARD_BASE}/api/trpc"

# Invite link format pulled from the "Copy Invite Link" button's onClick in
# chunk 164: `${appUrl}/invitation?token=${token}`.
INVITE_URL_TEMPLATE = f"{DASHBOARD_BASE}/invitation?token={{token}}"

# Valid role values from the bundle (chunks reference `n.X.ADMIN`, `n.X.MEMBER`).
VALID_ROLES = ("ADMIN", "MEMBER")


# ---------------------------------------------------------------------------
# Low-level helpers — one-shot HTTP with the engine-resolved cookie header
# ---------------------------------------------------------------------------


def _merge_headers(*, cookie_header: str | None, extra: dict | None = None) -> dict:
    """Build a browser-ish request header dict with our Cookie header pinned."""
    hdrs = http.headers(waf="vercel", accept="json", extra=extra or {})
    out = dict(hdrs.get("headers", {}))
    if cookie_header:
        out["Cookie"] = cookie_header
    return out


async def _dashboard_get(path: str, *, cookie_header: str, extra: dict | None = None) -> dict:
    url = path if path.startswith("http") else f"{DASHBOARD_BASE}{path}"
    headers = _merge_headers(cookie_header=cookie_header, extra=extra)
    return await http.get(url, headers=headers, http2=False)


async def _dashboard_post(path: str, *, cookie_header: str, json_body: dict | None = None,
                          data: dict | None = None, extra: dict | None = None) -> dict:
    url = path if path.startswith("http") else f"{DASHBOARD_BASE}{path}"
    headers = _merge_headers(cookie_header=cookie_header, extra=extra)
    if json_body is not None:
        return await http.post(url, json=json_body, headers=headers, http2=False)
    return await http.post(url, data=data or {}, headers=headers, http2=False)


async def _backend_request(method: str, path: str, *, bearer: str,
                           json_body: dict | None = None, extra: dict | None = None) -> dict:
    """Call the Greptile backend API (api.greptile.com) with the greptileToken."""
    url = path if path.startswith("http") else f"https://api.greptile.com{path}"
    headers = dict(http.headers(accept="json").get("headers", {}))
    headers["Authorization"] = f"Bearer {bearer}"
    if extra:
        headers.update(extra)
    method = method.upper()
    if method == "GET":
        return await http.get(url, headers=headers)
    if method == "POST":
        return await http.post(url, json=json_body or {}, headers=headers)
    if method == "PATCH":
        return await http.patch(url, json=json_body or {}, headers=headers)
    if method == "DELETE":
        return await http.delete(url, headers=headers)
    if method == "PUT":
        return await http.put(url, json=json_body or {}, headers=headers)
    raise ValueError(f"Unsupported method: {method}")


async def _get_session(cookie_header: str) -> dict | None:
    """Hit /api/auth/session and return {user, expires} or None."""
    resp = await _dashboard_get("/api/auth/session", cookie_header=cookie_header)
    if resp.get("status") != 200:
        return None
    data = resp.get("json")
    if isinstance(data, dict) and data.get("user"):
        return data
    return None


async def _require_session(cookie_header: str) -> dict:
    """Return the session dict or raise SESSION_EXPIRED so the engine retries."""
    session = await _get_session(cookie_header)
    if not session:
        raise RuntimeError(
            "SESSION_EXPIRED: Greptile dashboard session is missing or invalid — "
            "log in at https://app.greptile.com to refresh."
        )
    return session


def _org_from_session(session: dict) -> dict:
    user = session.get("user", {}) or {}
    current = user.get("currentTenantExternalId")
    orgs = user.get("organizations") or []
    if current:
        for o in orgs:
            if o.get("tenantExternalId") == current:
                return o
    return orgs[0] if orgs else {}


def _greptile_account_from_user(user: dict, org: dict) -> dict:
    """Map the logged-in user + current org into an account shape."""
    return {
        "id": f"greptile:{user.get('greptileId')}",
        "issuer": "greptile.com",
        "identifier": user.get("email") or "",
        "email": user.get("email"),
        "handle": user.get("email"),
        "displayName": user.get("name") or user.get("email"),
        "image": user.get("image"),
        "accountType": (org.get("role") or "MEMBER").lower(),
        "isActive": True,
        "url": f"{DASHBOARD_BASE}/settings/organization/people",
    }


def _member_to_account(item: dict) -> dict:
    """Map a searchPeople item into an `account` shape dict.

    Items look like: {email, role, token, type}. `type` is `"member"` for real
    org members and `"invite"` for pending email invites. `token` is non-null
    only on invite rows — use that as a second signal.

    Pending invites get `accountType:"invite"` + `isActive:false` so callers
    can tell them apart from real members without inspecting a `type` field
    that isn't part of the account shape.
    """
    email = item.get("email") or ""
    role = item.get("role") or "MEMBER"
    itype = (item.get("type") or "member").lower()
    is_invite = itype == "invite" or bool(item.get("token"))
    return {
        "issuer": "greptile.com",
        "identifier": email,
        "email": email,
        "handle": email,
        "displayName": email,
        "accountType": "invite" if is_invite else role.lower(),
        "isActive": not is_invite,
        "url": f"{DASHBOARD_BASE}/settings/organization/people",
    }


def _item_to_invitation(item: dict, tenant_external_id: str) -> dict:
    """Map a searchPeople invite row into an `invitation` shape dict."""
    email = item.get("email") or ""
    token = item.get("token") or ""
    return {
        "id": token or email,
        "invitationType": "organization",
        "email": email,
        "role": (item.get("role") or "MEMBER").lower(),
        "status": "pending",
        "token": token,
        "url": f"{DASHBOARD_BASE}/settings/organization/people",
    }


def _normalize_role(role: str | None) -> str:
    """Uppercase + validate a role string. Raises on unknown roles."""
    if not role:
        return "MEMBER"
    r = role.strip().upper()
    if r not in VALID_ROLES:
        raise ValueError(f"Invalid role {role!r}; expected one of {VALID_ROLES}")
    return r


# ---------------------------------------------------------------------------
# tRPC helpers — GET for queries, POST for mutations. All requests hit
# /api/trpc/<procedure> and use the "superjson" envelope `{json: {...}}`.
# ---------------------------------------------------------------------------


async def _trpc_query(procedure: str, input_args: dict, *, cookie_header: str) -> dict:
    """GET /api/trpc/<procedure>?input=<urlencoded json>."""
    payload = json.dumps({"json": input_args}, separators=(",", ":"))
    url = http.build_url(f"{TRPC_BASE}/{procedure}", params={"input": payload})
    headers = _merge_headers(cookie_header=cookie_header)
    return await http.get(url, headers=headers, http2=False)


async def _trpc_mutate(procedure: str, input_args: dict, *, cookie_header: str) -> dict:
    """POST /api/trpc/<procedure> with {json: {...}} body."""
    url = f"{TRPC_BASE}/{procedure}"
    headers = _merge_headers(cookie_header=cookie_header, extra={"content-type": "application/json"})
    return await http.post(url, json={"json": input_args}, headers=headers, http2=False)


def _unwrap_trpc(resp: dict, *, procedure: str) -> dict:
    """Return the inner `result.data.json` payload or raise with the tRPC error.

    Shape: {"result":{"data":{"json":<payload>}}} on success.
             {"error":{"json":{"message":...,"code":...}}} on failure.
    """
    status = resp.get("status")
    body = resp.get("json")
    if not isinstance(body, dict):
        raise RuntimeError(
            f"tRPC {procedure} returned non-JSON body (status={status}): "
            f"{str(resp.get('body'))[:200]}"
        )
    if "error" in body:
        err = body["error"]
        inner = err.get("json") if isinstance(err, dict) else None
        msg = (inner or {}).get("message") or str(err)
        code = (inner or {}).get("code") or (inner or {}).get("data", {}).get("code")
        raise RuntimeError(f"tRPC {procedure} failed ({code}, status={status}): {msg}")
    if status and status >= 400:
        raise RuntimeError(f"tRPC {procedure} HTTP {status}: {str(resp.get('body'))[:200]}")
    try:
        return body["result"]["data"]["json"]
    except (KeyError, TypeError) as e:
        raise RuntimeError(f"tRPC {procedure} unexpected envelope: {body!r}") from e


async def _resolve_tenant_id(cookie_header: str, tenant_id: str | None = None) -> str:
    """Return the tenant external id — provided, else from session."""
    if tenant_id:
        return tenant_id
    session = await _require_session(cookie_header)
    org = _org_from_session(session)
    tid = org.get("tenantExternalId")
    if not tid:
        raise RuntimeError("Could not resolve tenant external id from session")
    return tid


# ---------------------------------------------------------------------------
# check_session — identity probe. Wired to connections.dashboard.auth.account.check
# ---------------------------------------------------------------------------


@returns({"authenticated": "boolean", "identifier": "string", "display": "string"})
@connection("dashboard")
@timeout(15)
async def check_session(*, auth: dict = None, **params) -> dict:
    """Verify Greptile dashboard session and identify the logged-in user + current org."""
    cookies = (auth or {}).get("cookies", "")
    session = await _get_session(cookies)
    if not session:
        return {"__result__": {"authenticated": False, "identifier": None, "display": None}}
    user = session.get("user", {}) or {}
    org = _org_from_session(session)
    label = user.get("email")
    if org.get("name"):
        label = f"{user.get('email')} @ {org['name']} ({org.get('role','MEMBER')})"
    return {"__result__": {
        "authenticated": True,
        "identifier": user.get("email"),
        "display": label,
    }}


# ---------------------------------------------------------------------------
# Member management — the primary surface of this skill. All routes go through
# /api/trpc on the dashboard host. Procedures captured from bundle spelunking;
# see the readme "People / Org API" table.
# ---------------------------------------------------------------------------


@returns("account[]")
@connection("dashboard")
@timeout(30)
async def list_members(*, tenant_external_id: str = None, query: str = "",
                       role: str = None, page: int = 0, page_size: int = 100,
                       auth: dict = None, **params) -> dict:
    """List active members of the current Greptile organization.

    Calls `organization.searchPeople` and returns only real members (type=member)
    as `account` shapes. Pending invites are excluded — use `list_invites` for those.

    Args:
        tenant_external_id: Override the org id (defaults to current session org).
        query: Optional email search filter.
        role: Optional role filter (`ADMIN` or `MEMBER`). `None` returns all.
        page: Zero-indexed page.
        page_size: Rows per page (default 100).
    """
    cookies = (auth or {}).get("cookies", "")
    tid = await _resolve_tenant_id(cookies, tenant_external_id)
    args: dict = {
        "tenantExternalId": tid,
        "query": query or "",
        "page": page,
        "pageSize": page_size,
    }
    if role:
        args["roles"] = [_normalize_role(role)]
    resp = await _trpc_query("organization.searchPeople", args, cookie_header=cookies)
    data = _unwrap_trpc(resp, procedure="organization.searchPeople")
    items = data.get("items") or []
    members = [it for it in items if (it.get("type") or "").lower() == "member"]
    accounts = [_member_to_account(it) for it in members]
    return {"__result__": accounts}


@returns("invitation[]")
@connection("dashboard")
@timeout(30)
async def list_invites(*, tenant_external_id: str = None, query: str = "",
                       page: int = 0, page_size: int = 100,
                       auth: dict = None, **params) -> dict:
    """List pending invitations in the current Greptile organization.

    Calls `organization.searchPeople` and returns only invite rows as
    `invitation` shapes. Active members are excluded — use `list_members`.

    Args:
        tenant_external_id: Override the org id (defaults to current session org).
        query: Optional email search filter.
        page: Zero-indexed page.
        page_size: Rows per page (default 100).
    """
    cookies = (auth or {}).get("cookies", "")
    tid = await _resolve_tenant_id(cookies, tenant_external_id)
    args: dict = {
        "tenantExternalId": tid,
        "query": query or "",
        "page": page,
        "pageSize": page_size,
    }
    resp = await _trpc_query("organization.searchPeople", args, cookie_header=cookies)
    data = _unwrap_trpc(resp, procedure="organization.searchPeople")
    items = data.get("items") or []
    invites = [it for it in items if (it.get("type") or "").lower() == "invite"
               or bool(it.get("token"))]
    return {"__result__": [_item_to_invitation(it, tid) for it in invites]}


@returns({"inviteUrl": "string", "token": "string", "defaultRole": "string",
          "tenantName": "string"})
@connection("dashboard")
@timeout(30)
async def get_invite_link(*, tenant_external_id: str = None,
                          auth: dict = None, **params) -> dict:
    """Fetch the current shareable org invite link.

    Calls `invitation.getOrganizationInviteLink` and assembles the full URL
    using the captured template `{appUrl}/invitation?token={token}`.
    """
    cookies = (auth or {}).get("cookies", "")
    tid = await _resolve_tenant_id(cookies, tenant_external_id)
    resp = await _trpc_query("invitation.getOrganizationInviteLink",
                             {"tenantExternalId": tid}, cookie_header=cookies)
    data = _unwrap_trpc(resp, procedure="invitation.getOrganizationInviteLink")
    token = data.get("token") or ""
    return {"__result__": {
        "inviteUrl": INVITE_URL_TEMPLATE.format(token=token) if token else "",
        "token": token,
        "defaultRole": data.get("defaultRole") or "MEMBER",
        "tenantName": (data.get("tenant") or {}).get("name") or "",
    }}


@returns({"inviteUrl": "string", "token": "string", "defaultRole": "string"})
@connection("dashboard")
@timeout(30)
async def create_invite_link(*, default_role: str = "MEMBER",
                             tenant_external_id: str = None,
                             auth: dict = None, **params) -> dict:
    """Create or rotate the org invite link.

    Calls `invitation.createOrganizationInviteLink` — if a link already exists
    this rotates the token. Returns the new fully-qualified URL.
    """
    cookies = (auth or {}).get("cookies", "")
    tid = await _resolve_tenant_id(cookies, tenant_external_id)
    args = {"tenantExternalId": tid, "defaultRole": _normalize_role(default_role)}
    resp = await _trpc_mutate("invitation.createOrganizationInviteLink", args,
                              cookie_header=cookies)
    data = _unwrap_trpc(resp, procedure="invitation.createOrganizationInviteLink")
    token = data.get("token") or ""
    return {"__result__": {
        "inviteUrl": INVITE_URL_TEMPLATE.format(token=token) if token else "",
        "token": token,
        "defaultRole": data.get("defaultRole") or _normalize_role(default_role),
    }}


@returns({"ok": "boolean", "revokedToken": "string"})
@connection("dashboard")
@timeout(30)
async def revoke_invite_link(*, tenant_external_id: str = None,
                             auth: dict = None, **params) -> dict:
    """Revoke the org invite link entirely. New invitees won't be able to join.

    Calls `invitation.revokeOrganizationInviteLink`.
    """
    cookies = (auth or {}).get("cookies", "")
    tid = await _resolve_tenant_id(cookies, tenant_external_id)
    resp = await _trpc_mutate("invitation.revokeOrganizationInviteLink",
                              {"tenantExternalId": tid}, cookie_header=cookies)
    data = _unwrap_trpc(resp, procedure="invitation.revokeOrganizationInviteLink")
    return {"__result__": {
        "ok": True,
        "revokedToken": (data or {}).get("token") or "",
    }}


@returns("invitation")
@connection("dashboard")
@timeout(30)
async def send_invite(*, email: str, role: str = "MEMBER",
                      tenant_external_id: str = None,
                      auth: dict = None, **params) -> dict:
    """Email an invite to join the Greptile org.

    Calls `invitation.create` — matches the "Invite by email" flow on the people
    settings page. Returns an `invitation` shape.

    Args:
        email: Address to invite.
        role: `ADMIN` or `MEMBER`. Defaults to `MEMBER`.
    """
    if not email:
        raise ValueError("email is required")
    cookies = (auth or {}).get("cookies", "")
    tid = await _resolve_tenant_id(cookies, tenant_external_id)
    clean_email = email.strip().lower()
    norm_role = _normalize_role(role)
    args = {
        "tenantExternalId": tid,
        "email": clean_email,
        "role": norm_role,
    }
    resp = await _trpc_mutate("invitation.create", args, cookie_header=cookies)
    _unwrap_trpc(resp, procedure="invitation.create")
    return {"__result__": {
        "id": clean_email,
        "invitationType": "organization",
        "email": clean_email,
        "role": norm_role.lower(),
        "status": "pending",
        "url": f"{DASHBOARD_BASE}/settings/organization/people",
    }}


@returns({"ok": "boolean", "email": "string", "role": "string"})
@connection("dashboard")
@timeout(30)
async def update_role(*, email: str, role: str,
                      tenant_external_id: str = None,
                      auth: dict = None, **params) -> dict:
    """Change a member's role in the current org.

    Calls `organization.setMemberRole`.

    Args:
        email: Member's email address.
        role: New role — `ADMIN` or `MEMBER`.
    """
    if not email:
        raise ValueError("email is required")
    if not role:
        raise ValueError("role is required")
    cookies = (auth or {}).get("cookies", "")
    tid = await _resolve_tenant_id(cookies, tenant_external_id)
    args = {
        "tenantExternalId": tid,
        "email": email.strip().lower(),
        "role": _normalize_role(role),
    }
    resp = await _trpc_mutate("organization.setMemberRole", args, cookie_header=cookies)
    _unwrap_trpc(resp, procedure="organization.setMemberRole")
    return {"__result__": {
        "ok": True,
        "email": args["email"],
        "role": args["role"],
    }}


@returns({"ok": "boolean", "email": "string"})
@connection("dashboard")
@timeout(30)
async def remove_member(*, email: str, tenant_external_id: str = None,
                        auth: dict = None, **params) -> dict:
    """Remove a member from the current org.

    Calls `organization.removeMember`. Arg shape `{email, tenantExternalId}`
    (captured from the bundle — no `namespaceExternalId`, which would scope it
    to a repo-level namespace instead of the org).
    """
    if not email:
        raise ValueError("email is required")
    cookies = (auth or {}).get("cookies", "")
    tid = await _resolve_tenant_id(cookies, tenant_external_id)
    args = {"email": email.strip().lower(), "tenantExternalId": tid}
    resp = await _trpc_mutate("organization.removeMember", args, cookie_header=cookies)
    _unwrap_trpc(resp, procedure="organization.removeMember")
    return {"__result__": {"ok": True, "email": args["email"]}}


@returns({"ok": "boolean", "email": "string"})
@connection("dashboard")
@timeout(30)
async def revoke_invite(*, email: str, tenant_external_id: str = None,
                        auth: dict = None, **params) -> dict:
    """Revoke a single pending email invite (not the shared link).

    Calls `invitation.revoke`. For the pending-invite rows in list_members.
    """
    if not email:
        raise ValueError("email is required")
    cookies = (auth or {}).get("cookies", "")
    tid = await _resolve_tenant_id(cookies, tenant_external_id)
    args = {"email": email.strip().lower(), "tenantExternalId": tid}
    resp = await _trpc_mutate("invitation.revoke", args, cookie_header=cookies)
    _unwrap_trpc(resp, procedure="invitation.revoke")
    return {"__result__": {"ok": True, "email": args["email"]}}


# ---------------------------------------------------------------------------
# Reverse-engineering helpers. Keep while the API surface is unstable.
# ---------------------------------------------------------------------------


@returns({"status": "integer", "url": "string", "headers": "object", "body": "string", "json": "object"})
@connection("dashboard")
@timeout(30)
async def probe(*, path: str, method: str = "GET", json_body: dict = None,
                extra_headers: dict = None, max_body: int = 4000,
                auth: dict = None, **params) -> dict:
    """Call an app.greptile.com path with the resolved session cookies.

    Args:
        path: Path or full URL.
        method: HTTP verb (GET, POST, PATCH, DELETE, PUT).
        json_body: JSON body for writes.
        extra_headers: Extra headers merged into the request.
        max_body: Body clip length (default 4000).
    """
    cookies = (auth or {}).get("cookies", "")
    url = path if path.startswith("http") else f"{DASHBOARD_BASE}{path}"
    headers = _merge_headers(cookie_header=cookies, extra=extra_headers or {})
    method = (method or "GET").upper()

    if method == "GET":
        resp = await http.get(url, headers=headers, http2=False)
    elif method == "POST":
        resp = await http.post(url, json=json_body or {}, headers=headers, http2=False)
    elif method == "PATCH":
        resp = await http.patch(url, json=json_body or {}, headers=headers, http2=False)
    elif method == "DELETE":
        if json_body is not None:
            resp = await http.delete(url, json=json_body, headers=headers, http2=False)
        else:
            resp = await http.delete(url, headers=headers, http2=False)
    elif method == "PUT":
        resp = await http.put(url, json=json_body or {}, headers=headers, http2=False)
    else:
        return {"__result__": {"error": f"Unsupported method: {method}"}}

    body = resp.get("body") or ""
    if isinstance(body, str) and len(body) > max_body:
        body = body[:max_body] + f"...[truncated {len(body)} bytes]"

    return {"__result__": {
        "status": resp.get("status"),
        "url": url,
        "headers": {k: v for k, v in (resp.get("headers") or {}).items()
                    if k.lower() in ("content-type", "set-cookie", "location",
                                     "x-powered-by", "server", "cache-control")},
        "body": body if not resp.get("json") else "",
        "json": resp.get("json"),
    }}


@returns({"status": "integer", "url": "string", "headers": "object",
          "body": "string", "json": "object"})
@connection("dashboard")
@timeout(30)
async def backend_probe(*, path: str, method: str = "GET", base: str = None,
                        json_body: dict = None, extra_headers: dict = None,
                        max_body: int = 4000, auth: dict = None, **params) -> dict:
    """Call the Greptile backend API with the greptileToken from the session.

    Args:
        path: Path or full URL on the backend.
        method: HTTP verb.
        base: Backend base URL override (defaults to https://api.greptile.com).
        json_body: JSON body for writes.
        extra_headers: Extra headers.
    """
    cookies = (auth or {}).get("cookies", "")
    session = await _require_session(cookies)
    user = session.get("user") or {}
    bearer = user.get("greptileToken") or ""
    if not bearer:
        return {"__result__": {"error": "No greptileToken on session"}}

    base = base or "https://api.greptile.com"
    url = path if path.startswith("http") else f"{base}{path}"
    headers = dict(http.headers(accept="json").get("headers", {}))
    headers["Authorization"] = f"Bearer {bearer}"
    if extra_headers:
        headers.update(extra_headers)

    method = (method or "GET").upper()
    if method == "GET":
        resp = await http.get(url, headers=headers)
    elif method == "POST":
        resp = await http.post(url, json=json_body or {}, headers=headers)
    elif method == "PATCH":
        resp = await http.patch(url, json=json_body or {}, headers=headers)
    elif method == "DELETE":
        resp = await http.delete(url, headers=headers)
    elif method == "PUT":
        resp = await http.put(url, json=json_body or {}, headers=headers)
    else:
        return {"__result__": {"error": f"Unsupported method: {method}"}}

    body = resp.get("body") or ""
    if isinstance(body, str) and len(body) > max_body:
        body = body[:max_body] + f"...[truncated {len(body)} bytes]"

    return {"__result__": {
        "status": resp.get("status"),
        "url": url,
        "headers": {k: v for k, v in (resp.get("headers") or {}).items()
                    if k.lower() in ("content-type", "set-cookie", "location",
                                     "x-powered-by", "server", "cache-control",
                                     "access-control-allow-origin")},
        "body": body if not resp.get("json") else "",
        "json": resp.get("json"),
    }}


@returns({"url": "string", "status": "integer", "size": "integer", "matches": "array"})
@connection("dashboard")
@timeout(60)
async def grep_bundle(*, path: str, patterns: list = None, context: int = 60,
                      max_matches: int = 120, auth: dict = None, **params) -> dict:
    """Fetch a (usually large) URL with session cookies and return regex matches.

    Designed for Next.js chunk spelunking: the raw body would be too large to round
    trip through the CLI renderer, so the skill runs the regexes itself and returns
    only the hits. Default patterns look for API URLs, fetch() calls, and
    server-action markers.

    Args:
        path: Path or full URL on the dashboard host.
        patterns: List of regex patterns. Defaults to a useful RE starter pack.
        context: Chars of surrounding context to include per match (default 60).
        max_matches: Cap per pattern to keep results bounded.
    """
    cookies = (auth or {}).get("cookies", "")
    url = path if path.startswith("http") else f"{DASHBOARD_BASE}{path}"
    headers = _merge_headers(cookie_header=cookies)
    resp = await http.get(url, headers=headers, http2=False)
    body = resp.get("body") or ""
    if not isinstance(body, str):
        body = str(body)

    default_patterns = [
        r"https?://api\.greptile\.com[^\"'\s<>`]{0,160}",
        r"https?://app\.greptile\.com/api/[^\"'\s<>`]{0,160}",
        r"\"/api/[^\"\s]{0,160}\"",
        r"\"/v[0-9]/[^\"\s]{0,160}\"",
        r"Next-Action\"\s*:\s*\"[0-9a-f]{40,}\"",
        r"\"/organizations/[^\"\s]{0,160}\"",
        r"\"/members[^\"\s]{0,160}\"",
        r"\"/invites?[^\"\s]{0,160}\"",
    ]
    pats = patterns or default_patterns

    out = []
    for pat in pats:
        try:
            rx = re.compile(pat)
        except re.error as e:
            out.append({"pattern": pat, "error": f"regex: {e}", "hits": []})
            continue
        hits = []
        for m in rx.finditer(body):
            if len(hits) >= max_matches:
                break
            start = max(0, m.start() - context)
            end = min(len(body), m.end() + context)
            hits.append({
                "match": m.group(0),
                "context": body[start:end],
                "pos": m.start(),
            })
        out.append({"pattern": pat, "count": len(hits), "hits": hits})

    return {"__result__": {
        "url": url,
        "status": resp.get("status"),
        "size": len(body),
        "matches": out,
    }}


@returns({"page_url": "string", "chunks_tried": "integer", "chunks_ok": "integer",
          "total_bytes": "integer", "matches": "array"})
@connection("dashboard")
@timeout(120)
async def grep_page_chunks(*, page: str, patterns: list = None, context: int = 80,
                           max_matches_per_pattern: int = 40,
                           auth: dict = None, **params) -> dict:
    """Fetch a dashboard page, extract every Next.js JS chunk, and grep them all.

    Consolidates the RE cycle: page → chunks → regex hits. Each hit is tagged with
    the chunk URL it came from so you can follow up by fetching the specific chunk.

    Args:
        page: Page path on the dashboard (e.g. /settings/organization/people).
        patterns: Regex list. Defaults to an API-endpoint starter pack.
        context: Surrounding chars included per hit.
        max_matches_per_pattern: Across all chunks combined.
    """
    cookies = (auth or {}).get("cookies", "")
    page_url = page if page.startswith("http") else f"{DASHBOARD_BASE}{page}"
    headers = _merge_headers(cookie_header=cookies)

    # 1. Fetch the HTML
    html_resp = await http.get(page_url, headers=headers, http2=False)
    html = html_resp.get("body") or ""
    if not isinstance(html, str):
        html = str(html)

    # 2. Extract chunk URLs from <script src="..."> tags
    chunk_re = re.compile(r'src="(/_next/static/chunks/[^"]+\.js)"')
    chunk_paths = list(dict.fromkeys(chunk_re.findall(html)))

    default_patterns = [
        r"https?://api\.greptile\.com[^\"'\s<>`()]{0,160}",
        r'"/v[0-9]/[a-zA-Z/_\-{}]{0,160}"',
        r'"/api/[a-zA-Z/_\-{}]{0,160}"',
        r'"/organizations/[a-zA-Z/_\-{}]{0,160}"',
        r'"/members[a-zA-Z/_\-{}]{0,160}"',
        r'"/invites?[a-zA-Z/_\-{}]{0,160}"',
        r'"/users?/[a-zA-Z/_\-{}]{0,160}"',
        r'"/tenants?/[a-zA-Z/_\-{}]{0,160}"',
        r'greptileToken',
    ]
    pats = patterns or default_patterns
    compiled = []
    for pat in pats:
        try:
            compiled.append((pat, re.compile(pat)))
        except re.error as e:
            compiled.append((pat, None))
    buckets = {pat: [] for pat, _ in compiled}

    chunks_ok = 0
    total_bytes = 0

    # 3. Fetch each chunk and grep
    for cpath in chunk_paths:
        curl = f"{DASHBOARD_BASE}{cpath}"
        try:
            r = await http.get(curl, headers=headers, http2=False)
        except Exception as e:
            continue
        if r.get("status") != 200:
            continue
        body = r.get("body") or ""
        if not isinstance(body, str):
            continue
        chunks_ok += 1
        total_bytes += len(body)

        for pat, rx in compiled:
            if rx is None:
                continue
            bucket = buckets[pat]
            if len(bucket) >= max_matches_per_pattern:
                continue
            for m in rx.finditer(body):
                if len(bucket) >= max_matches_per_pattern:
                    break
                start = max(0, m.start() - context)
                end = min(len(body), m.end() + context)
                bucket.append({
                    "chunk": cpath,
                    "match": m.group(0),
                    "context": body[start:end].replace("\n", " "),
                })

    matches = [{"pattern": pat, "count": len(hits), "hits": hits}
               for pat, hits in buckets.items()]

    return {"__result__": {
        "page_url": page_url,
        "chunks_tried": len(chunk_paths),
        "chunks_ok": chunks_ok,
        "total_bytes": total_bytes,
        "matches": matches,
    }}


@returns({"auth_keys": "array", "cookie_names": "array", "cookie_len": "integer", "cookie_header": "string"})
@connection("dashboard")
@timeout(10)
async def inspect_auth(*, auth: dict = None, **params) -> dict:
    """Debug: return the engine-resolved cookie header verbatim."""
    auth = auth or {}
    cookies = auth.get("cookies", "") or ""
    names = []
    if isinstance(cookies, str) and cookies:
        for part in cookies.split(";"):
            p = part.strip()
            if "=" in p:
                names.append(p.split("=", 1)[0])
    return {"__result__": {
        "auth_keys": list(auth.keys()),
        "cookie_names": names,
        "cookie_len": len(cookies) if isinstance(cookies, str) else 0,
        "cookie_header": cookies if isinstance(cookies, str) else "",
    }}
