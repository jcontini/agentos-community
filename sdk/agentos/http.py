"""HTTP client utilities for skills.

Provides a pre-configured httpx client with proper cookie jar handling.
Skills should use client() instead of building their own httpx.Client —
it handles cookie parsing, HTTP/2, timeouts, and standard headers.
"""

import httpx

_DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_JSON_HEADERS = {
    "User-Agent": _DEFAULT_HEADERS["User-Agent"],
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}


def parse_cookies(cookie_header: str | None) -> httpx.Cookies:
    """Parse a raw Cookie header string into an httpx cookie jar.

    Using a cookie jar instead of a raw header lets httpx track Set-Cookie
    responses automatically — critical for multi-step flows where the server
    refreshes session cookies (CSRF forms, login redirects).
    """
    jar = httpx.Cookies()
    if not cookie_header:
        return jar
    for part in cookie_header.split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            name, val = part.split("=", 1)
            jar.set(name.strip(), val.strip())
    return jar


def client(
    cookies: str | httpx.Cookies | None = None,
    *,
    headers: dict | None = None,
    json_api: bool = False,
    timeout: float = 30.0,
    http2: bool = True,
) -> httpx.Client:
    """Create a pre-configured httpx Client.

    Args:
        cookies: Raw cookie header string or httpx.Cookies jar.
        headers: Extra headers to merge with defaults.
        json_api: Use JSON Accept header instead of HTML.
        timeout: Request timeout in seconds.
        http2: Enable HTTP/2.
    """
    base_headers = dict(_JSON_HEADERS if json_api else _DEFAULT_HEADERS)
    if headers:
        base_headers.update(headers)

    cookie_jar = None
    if isinstance(cookies, str):
        cookie_jar = parse_cookies(cookies)
    elif isinstance(cookies, httpx.Cookies):
        cookie_jar = cookies

    return httpx.Client(
        http2=http2,
        follow_redirects=True,
        timeout=timeout,
        headers=base_headers,
        cookies=cookie_jar,
    )


def get_cookies(params: dict | None) -> str | None:
    """Extract cookie header from the runtime params dict.

    Standard pattern for skills that receive params with auth:
        cookie_header = get_cookies(params)
        with client(cookies=cookie_header) as c:
            ...
    """
    if not params:
        return None
    auth = params.get("auth")
    if not auth:
        return None
    cookies = auth.get("cookies") or ""
    return cookies if cookies else None
