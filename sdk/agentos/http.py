"""HTTP client for skills — routes all requests through the engine.

All HTTP goes through the engine via dispatch. The engine handles:
- Header profiles (default, json, api, navigate) for WAF bypass
- Cookie jar management and writeback
- HTTP/1.1 vs HTTP/2 toggle
- Request/response logging to engine-io.jsonl
- Domain allowlisting (future: firewall rules)

Simple requests:
    from agentos import http
    resp = http.get("https://api.example.com/data", profile="api")
    data = resp["json"]

Session with cookie jar:
    with http.client(cookies=cookie_header, profile="navigate") as c:
        c.get("https://www.amazon.com/")  # warm session
        resp = c.get("https://www.amazon.com/gp/your-account/order-history")
        orders = resp["body"]
"""

from __future__ import annotations

from agentos._bridge import dispatch


# ---------------------------------------------------------------------------
# Simple requests — stateless, no cookie jar
# ---------------------------------------------------------------------------


def get(url: str, **kwargs) -> dict:
    """HTTP GET request. Returns dict with status, ok, url, headers, body, json."""
    return dispatch("__http_request__", {"method": "GET", "url": url, **kwargs})


def post(url: str, **kwargs) -> dict:
    """HTTP POST request. Accepts json=, data=, headers=, cookies=, profile=, etc."""
    return dispatch("__http_request__", {"method": "POST", "url": url, **kwargs})


def put(url: str, **kwargs) -> dict:
    """HTTP PUT request."""
    return dispatch("__http_request__", {"method": "PUT", "url": url, **kwargs})


def delete(url: str, **kwargs) -> dict:
    """HTTP DELETE request."""
    return dispatch("__http_request__", {"method": "DELETE", "url": url, **kwargs})


def patch(url: str, **kwargs) -> dict:
    """HTTP PATCH request."""
    return dispatch("__http_request__", {"method": "PATCH", "url": url, **kwargs})


def head(url: str, **kwargs) -> dict:
    """HTTP HEAD request."""
    return dispatch("__http_request__", {"method": "HEAD", "url": url, **kwargs})


# ---------------------------------------------------------------------------
# Session client — cookie jar with writeback
# ---------------------------------------------------------------------------


def client(
    cookies: str | None = None,
    *,
    headers: dict | None = None,
    profile: str | None = None,
    skip_cookies: list[str] | None = None,
    timeout: float = 30.0,
    http2: bool = True,
) -> HttpSession:
    """Create an HTTP session with cookie jar tracking.

    Use as a context manager for multi-request flows where cookies matter:

        with http.client(cookies=auth["cookies"], profile="navigate") as c:
            c.get("https://www.amazon.com/")
            resp = c.get("https://www.amazon.com/gp/your-account/order-history")

    The engine tracks Set-Cookie responses and diffs the jar on close
    for automatic writeback to the credential store.
    """
    return HttpSession(
        cookies=cookies,
        headers=headers,
        profile=profile or "default",
        skip_cookies=skip_cookies,
        timeout=timeout,
        http2=http2,
    )


class HttpSession:
    """HTTP session with engine-managed cookie jar."""

    def __init__(self, **config):
        self._config = config
        self._session_id: str | None = None

    def __enter__(self):
        result = dispatch("__http_session_open__", self._config)
        self._session_id = result["session_id"]
        return self

    def __exit__(self, *_):
        if self._session_id:
            dispatch("__http_session_close__", {"session_id": self._session_id})
            self._session_id = None

    def get(self, url: str, **kwargs) -> dict:
        return self._request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> dict:
        return self._request("POST", url, **kwargs)

    def put(self, url: str, **kwargs) -> dict:
        return self._request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs) -> dict:
        return self._request("DELETE", url, **kwargs)

    def patch(self, url: str, **kwargs) -> dict:
        return self._request("PATCH", url, **kwargs)

    def _request(self, method: str, url: str, **kwargs) -> dict:
        return dispatch("__http_session_request__", {
            "session_id": self._session_id,
            "method": method,
            "url": url,
            **kwargs,
        })




# ---------------------------------------------------------------------------
# Skill helpers — kept as-is, used by all skills
# ---------------------------------------------------------------------------


def skill_error(message: str, **extra) -> dict:
    """Return a structured error dict from a skill operation."""
    result = {"error": message}
    result.update(extra)
    return {"__result__": result}


def skill_result(**fields) -> dict:
    """Return a structured result dict from a skill operation."""
    return {"__result__": fields}


def get_cookies(params: dict | None) -> str | None:
    """Extract cookie header from the runtime params dict."""
    if not params:
        return None
    auth = params.get("auth")
    if not auth:
        return None
    cookies = auth.get("cookies") or ""
    return cookies if cookies else None


def require_cookies(params: dict | None, op: str) -> str:
    """Extract cookie header or raise with a helpful message."""
    header = get_cookies(params)
    if not header:
        raise ValueError(f"{op} requires session cookies — sign in via the browser first")
    return header


def parse_cookie(cookie_header: str, name: str) -> str | None:
    """Extract a single cookie value from a header string."""
    for part in cookie_header.split(";"):
        k, _, v = part.strip().partition("=")
        if k == name:
            return v or None
    return None


def skill_secret(
    domain: str,
    identifier: str,
    item_type: str,
    value: dict,
    *,
    source: str | None = None,
    label: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """Build a __secrets__ entry for credential storage."""
    entry = {
        "domain": domain,
        "identifier": identifier,
        "item_type": item_type,
        "value": value,
    }
    if source:
        entry["source"] = source
    if label:
        entry["label"] = label
    if metadata:
        entry["metadata"] = metadata
    return entry
