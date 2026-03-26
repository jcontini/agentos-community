"""HTTP client utilities for skills.

Provides pre-configured httpx clients with proper cookie handling and
header profiles for different anti-bot protection tiers.

Profiles (from docs/reverse-engineering/1-transport/):
  - default: Basic browser headers — works for most APIs
  - api:     CORS/JSON headers + Sec-CH-UA — for CDN-protected XHR/fetch
  - navigate: Full client hints + Sec-Fetch navigation — for protected
              HTML pages (Amazon Lightsaber, authenticated page scraping)

Skills should use client() instead of building their own httpx.Client.
"""

import httpx

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/145.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# Header profiles — three tiers of anti-bot headers
# ---------------------------------------------------------------------------

_DEFAULT_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_JSON_HEADERS = {
    "User-Agent": _UA,
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

# CDN/API profile: passes Cloudflare + CloudFront WAF checks for XHR
_API_HEADERS = {
    "User-Agent": _UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Ch-Ua": '"Chromium";v="145", "Not:A-Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
}

# Full navigation profile: passes Amazon Lightsaber, all CDN checks
# Includes client hints (Device-Memory, Downlink, Rtt, Ect, Dpr)
# that most scraping guides miss but Amazon/eBay fingerprint.
_NAVIGATE_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Cache-Control": "max-age=0",
    # Network quality hints
    "Device-Memory": "8",
    "Downlink": "10",
    "Dpr": "2",
    "Ect": "4g",
    "Rtt": "50",
    # Structured client hints
    "Sec-Ch-Device-Memory": "8",
    "Sec-Ch-Dpr": "2",
    "Sec-Ch-Ua": '"Chromium";v="145", "Not:A-Brand";v="99"',
    "Sec-Ch-Ua-Full-Version-List": '"Chromium";v="145.0.7632.6", "Not:A-Brand";v="99.0.0.0"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Ch-Viewport-Width": "1512",
    # Navigation fetch metadata
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Viewport-Width": "1512",
}

_PROFILES = {
    "default": _DEFAULT_HEADERS,
    "json": _JSON_HEADERS,
    "api": _API_HEADERS,
    "navigate": _NAVIGATE_HEADERS,
}


# ---------------------------------------------------------------------------
# Cookie utilities
# ---------------------------------------------------------------------------


def parse_cookies(
    cookie_header: str | None,
    *,
    skip: set[str] | None = None,
) -> httpx.Cookies:
    """Parse a raw Cookie header string into an httpx cookie jar.

    Using a cookie jar instead of a raw header lets httpx track Set-Cookie
    responses automatically — critical for multi-step flows where the server
    refreshes session cookies (CSRF forms, login redirects).

    Args:
        cookie_header: Raw "name=val; name2=val2" string.
        skip: Cookie names to filter out. Use this to strip cookies that
              trigger client-side features (e.g. Amazon's Siege encryption
              via csd-key). See docs/reverse-engineering/1-transport/.
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
            name = name.strip()
            if skip and name in skip:
                continue
            jar.set(name, val.strip())
    return jar


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------


def client(
    cookies: str | httpx.Cookies | None = None,
    *,
    headers: dict | None = None,
    profile: str | None = None,
    json_api: bool = False,
    skip_cookies: set[str] | None = None,
    timeout: float = 30.0,
    http2: bool = True,
) -> httpx.Client:
    """Create a pre-configured httpx Client.

    Args:
        cookies: Raw cookie header string or httpx.Cookies jar.
        headers: Extra headers to merge with profile defaults.
        profile: Header profile — "default", "api", "navigate", or "json".
                 "api" adds Sec-CH-UA/Sec-Fetch for CDN-protected APIs.
                 "navigate" adds full client hints for protected HTML pages.
                 Defaults to "json" if json_api=True, else "default".
        json_api: Shorthand for profile="json". Kept for backward compat.
        skip_cookies: Cookie names to filter out before sending. Useful for
                      stripping cookies that trigger client-side encryption
                      (e.g. Amazon's csd-key for Siege decryption).
        timeout: Request timeout in seconds.
        http2: Enable HTTP/2. Set False for Vercel Security Checkpoint.
    """
    # Resolve profile
    if profile is None:
        profile = "json" if json_api else "default"
    base_headers = dict(_PROFILES.get(profile, _DEFAULT_HEADERS))
    if headers:
        base_headers.update(headers)

    # Build cookie jar
    cookie_jar = None
    if isinstance(cookies, str):
        cookie_jar = parse_cookies(cookies, skip=skip_cookies)
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
