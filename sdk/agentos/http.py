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
# Deprecated: surf() — use http.get()/http.client() instead
# Kept temporarily for migration. Will be removed once all skills migrate.
# ---------------------------------------------------------------------------

# Deferred import to avoid pulling in httpx when skills use the new API.
_httpx = None
_tracked_clients: list = []


def _get_httpx():
    global _httpx
    if _httpx is None:
        import httpx
        _httpx = httpx
    return _httpx


def _snapshot_jar(cookies) -> dict[tuple[str, str], str]:
    result = {}
    for cookie in cookies.jar:
        domain = cookie.domain.lstrip(".")
        result[(cookie.name, domain)] = cookie.value
    return result


def _collect_cookie_writeback() -> list[dict] | None:
    changes = []
    for initial, client in _tracked_clients:
        current = _snapshot_jar(client.cookies)
        for (name, domain), value in current.items():
            if initial.get((name, domain)) != value:
                changes.append({"name": name, "value": value, "domain": domain})
    _tracked_clients.clear()
    return changes if changes else None


def parse_cookies(
    cookie_header: str | None,
    *,
    skip: set[str] | None = None,
):
    httpx = _get_httpx()
    jar = httpx.Cookies()
    if not cookie_header:
        return jar
    for part in cookie_header.split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            name, val = part.split("=", 1)
            name = name.strip()
            if skip and name in skip:
                continue
            jar.set(name, val.strip())
    return jar


def surf(
    cookies=None,
    *,
    headers: dict | None = None,
    profile: str | None = None,
    json_api: bool = False,
    skip_cookies: set[str] | None = None,
    timeout: float = 30.0,
    http2: bool = True,
):
    """DEPRECATED: Use http.get()/http.client() instead. Will be removed."""
    httpx = _get_httpx()

    _PROFILES = {
        "default": {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
        "json": {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        },
        "api": {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Ch-Ua": '"Chromium";v="145", "Not:A-Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
        },
        "navigate": {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Cache-Control": "max-age=0",
            "Device-Memory": "8",
            "Downlink": "10",
            "Dpr": "2",
            "Ect": "4g",
            "Rtt": "50",
            "Sec-Ch-Device-Memory": "8",
            "Sec-Ch-Dpr": "2",
            "Sec-Ch-Ua": '"Chromium";v="145", "Not:A-Brand";v="99"',
            "Sec-Ch-Ua-Full-Version-List": '"Chromium";v="145.0.7632.6", "Not:A-Brand";v="99.0.0.0"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Ch-Viewport-Width": "1512",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "Viewport-Width": "1512",
        },
    }

    if profile is None:
        profile = "json" if json_api else "default"
    base_headers = dict(_PROFILES.get(profile, _PROFILES["default"]))
    if headers:
        lower_map = {k.lower(): k for k in base_headers}
        for k, v in headers.items():
            existing = lower_map.get(k.lower())
            if existing and existing != k:
                del base_headers[existing]
            base_headers[k] = v
            lower_map[k.lower()] = k

    cookie_jar = None
    if isinstance(cookies, str):
        cookie_jar = parse_cookies(cookies, skip=skip_cookies)
    elif isinstance(cookies, httpx.Cookies):
        cookie_jar = cookies

    client = httpx.Client(
        http2=http2,
        follow_redirects=True,
        timeout=timeout,
        headers=base_headers,
        cookies=cookie_jar,
    )

    if cookie_jar is not None:
        _tracked_clients.append((_snapshot_jar(client.cookies), client))

    return client


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
