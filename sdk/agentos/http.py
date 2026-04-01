"""HTTP client for skills — routes all requests through the engine.

All HTTP goes through the engine via dispatch. The engine handles:
- Cookie jar management and writeback
- HTTP/1.1 vs HTTP/2 toggle
- Request/response logging to engine-io.jsonl
- Domain allowlisting (future: firewall rules)

Headers are built in Python via http.headers() — the engine is pure transport.

Simple requests:
    from agentos import http
    resp = http.get("https://api.example.com/data", **http.headers(accept="json"))
    data = resp["json"]

Session with cookie jar:
    with http.client(cookies=cookie_header) as c:
        c.get("https://www.amazon.com/", **http.headers(waf="cf", mode="navigate", accept="html"))
        resp = c.get("https://www.amazon.com/gp/your-account/order-history",
                      **http.headers(waf="cf", mode="navigate", accept="html"))
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
    skip_cookies: list[str] | None = None,
    timeout: float = 30.0,
    http2: bool = True,
    retry: int = 0,
    retry_delay: float = 2.0,
) -> HttpSession:
    """Create an HTTP session with cookie jar tracking.

    Use as a context manager for multi-request flows where cookies matter:

        with http.client(cookies=cookie_header) as c:
            c.get("https://www.amazon.com/", **http.headers(waf="cf", mode="navigate", accept="html"))
            resp = c.get("https://www.amazon.com/gp/your-account/order-history",
                          **http.headers(waf="cf", mode="navigate", accept="html"))

    The engine tracks Set-Cookie responses and diffs the jar on close
    for automatic writeback to the credential store.
    """
    return HttpSession(
        cookies=cookies,
        headers=headers,
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
# Header composition — independent knobs, no engine profiles
# ---------------------------------------------------------------------------


_UA = {
    "chrome-desktop": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "chrome-mobile": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/131.0.0.0 Mobile/15E148 Safari/604.1",
    "safari-desktop": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
}

_WAF = {
    "cf": {
        # Covers CloudFront (AWS) and Cloudflare — same signals today.
        "hints": {
            "Sec-CH-UA": '"Chromium";v="131", "Not:A-Brand";v="99"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"macOS"',
        },
        "http2": True,
    },
    "vercel": {
        # Vercel checkpoint blocks HTTP/2 with 429.
        "hints": {},
        "http2": False,
    },
}

_MODE = {
    "fetch": {
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    },
    "navigate": {
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
        "Device-Memory": "8",
        "Downlink": "10",
        "DPR": "2",
        "ECT": "4g",
        "RTT": "50",
        "Viewport-Width": "1512",
    },
}

_ACCEPT = {
    "json": {"Accept": "application/json"},
    "html": {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
    "any": {"Accept": "*/*"},
}


def headers(*, waf=None, ua="chrome-desktop", mode="fetch", accept="any", extra=None):
    """Build request headers from independent knobs.

    Returns dict with "headers" and optionally "http2". Spread into
    http.get/post/client with **: http.get(url, **http.headers(...))

    Knobs (ordered by network layer):
        waf:    WAF vendor — "cf", "vercel", or None (default).
        ua:     User-Agent — "chrome-desktop", "chrome-mobile",
                "safari-desktop", or a raw UA string.
        mode:   Request type — "fetch" (default) or "navigate".
                Sec-Fetch-* headers added only when waf is set.
        accept: Content — "json", "html", or "any" (default).
        extra:  Additional headers merged last (highest priority).
    """
    h = {}
    result = {}

    # Standard — every request gets baseline browser headers
    h["User-Agent"] = _UA.get(ua, ua)
    h["Accept-Language"] = "en-US,en;q=0.9"
    h["Accept-Encoding"] = "gzip, deflate, br, zstd"

    # Transport — WAF vendor client hints + protocol
    if waf:
        waf_config = _WAF[waf]
        h.update(waf_config["hints"])
        result["http2"] = waf_config["http2"]

    # Request — Sec-Fetch-* metadata (only when WAF is checking)
    if waf:
        h.update(_MODE[mode])

    # Content — what format you want back
    h.update(_ACCEPT[accept])

    # Extra — custom headers merge last, can override anything
    if extra:
        h.update(extra)

    result["headers"] = h
    return result


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
