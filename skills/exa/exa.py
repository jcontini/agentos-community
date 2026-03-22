"""
exa.py — Dashboard auth and API key management for Exa

Auth architecture (discovered via Playwright reverse engineering):
  - Auth domain:      auth.exa.ai (NextAuth.js / Auth.js)
  - Dashboard domain: dashboard.exa.ai
  - Login method:     Email verification code (6-digit, NOT a magic link)
  - Session:          JWT in `next-auth.session-token` cookie (.exa.ai)
  - Protection:       Vercel Security Checkpoint on dashboard.exa.ai
  - Transport:        httpx http2=False for dashboard API calls
                      (Vercel checkpoint blocks httpx's h2 JA4 fingerprint;
                      h1 passes regardless of cookies or headers)

Login flow (fully HTTPX, no browser needed):
  1. send_login_code(email)    [HTTPX]
     - GET  auth.exa.ai/api/auth/csrf       → CSRF token + cookie
     - POST auth.exa.ai/api/auth/signin/email → triggers verification code email

  2. Agent retrieves 6-digit code from email (any provider)

  3. verify_login_code(email, code)   [HTTPX]
     - POST auth.exa.ai/api/verify-otp     → {hashedOtp, rawOtp}
     - Construct token = hashedOtp:rawOtp
     - GET  auth.exa.ai/api/auth/callback/email?token=...&email=...
       → sets next-auth.session-token cookie
     - Validates session, stores cookies via __secrets__

Dashboard API (authenticated, cookie-based):
  GET /api/auth/session         → { user: { email, id, currentTeamId, teams }, expires }
  GET /api/get-api-keys         → { apiKeys: [{ id, name, enabled, ... }] }
  GET /api/get-teams            → { teams: [{ id, name, role, customRateLimit, ... }] }
  GET /api/service-api-keys     → { serviceApiKeys: [...] }
  GET /api/get-websets-billing   → { hasAccess: bool }

Key discovery: the `id` field in get-api-keys IS the full API key value.
The dashboard UI masks it, but the API returns it in full.
Key format: UUID (e.g. "5bcbb3da-e415-44f1-8e57-10e92177f378").
"""

import json
import urllib.parse
import httpx

AUTH_BASE = "https://auth.exa.ai"
DASHBOARD_BASE = "https://dashboard.exa.ai"
CALLBACK_URL = "https://dashboard.exa.ai/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Sec-CH-UA": '"Chromium";v="145", "Google Chrome";v="145", "Not-A.Brand";v="99"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"macOS"',
}


def _get_csrf_token(client: httpx.Client) -> str:
    """Fetch CSRF token from NextAuth. Sets the csrf cookie on the client."""
    resp = client.get(f"{AUTH_BASE}/api/auth/csrf")
    resp.raise_for_status()
    data = resp.json()
    return data["csrfToken"]


def _send_verification_email(client: httpx.Client, csrf_token: str, email: str) -> dict:
    """POST to NextAuth email signin endpoint to trigger the verification code email."""
    resp = client.post(
        f"{AUTH_BASE}/api/auth/signin/email",
        data={
            "email": email,
            "csrfToken": csrf_token,
            "callbackUrl": CALLBACK_URL,
            "json": "true",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    return resp.json()


def _check_session(client: httpx.Client) -> dict | None:
    """Check the current session on the dashboard. Returns user data or None."""
    resp = client.get(f"{DASHBOARD_BASE}/api/auth/session")
    if resp.status_code != 200:
        return None
    data = resp.json()
    if data.get("user"):
        return data
    return None


def _serialize_cookies(client: httpx.Client) -> dict:
    """Extract exa.ai cookies from an HTTPX client as a serializable dict."""
    cookies = {}
    for cookie in client.cookies.jar:
        if "exa.ai" in cookie.domain:
            cookies[cookie.name] = cookie.value
    return cookies


# ---------------------------------------------------------------------------
# Operations — called by the Python executor with kwargs
# ---------------------------------------------------------------------------

def send_login_code(*, email: str, **params) -> dict:
    """Trigger a verification code email for the given address.

    After calling this, the agent must:
      1. Check the user's email for the 6-digit code (subject: 'Sign in to Exa Dashboard')
      2. Call exa.verify_login_code with the email and code
    """
    if not email:
        return {"__result__": {"error": "email is required"}}

    with httpx.Client(
        http2=False,
        follow_redirects=True,
        timeout=30,
        headers=HEADERS,
    ) as client:
        csrf_token = _get_csrf_token(client)
        _send_verification_email(client, csrf_token, email)

        # Save the CSRF cookies so verify_login_code can use the same session
        auth_cookies = _serialize_cookies(client)

    return {
        "__result__": {
            "status": "code_sent",
            "email": email,
            "hint": (
                "A 6-digit code was sent to the email. To complete login:\n"
                "1. Search email for subject 'Sign in to Exa Dashboard' from exa.ai\n"
                "2. Extract the 6-digit code\n"
                "3. Call exa.verify_login_code with the email and code"
            ),
            "_auth_cookies": auth_cookies,
        }
    }


def verify_login_code(*, email: str, code: str, **params) -> dict:
    """Verify the 6-digit code and complete login — fully HTTPX, no browser needed.

    Flow:
      1. POST /api/verify-otp with {email, otp} → {hashedOtp, rawOtp}
      2. Construct NextAuth callback token = hashedOtp:rawOtp
      3. GET /api/auth/callback/email?token=...&email=... → session cookie
      4. Validate session and store cookies via __secrets__
    """
    if not email or not code:
        return {"__result__": {"error": "email and code are required"}}

    with httpx.Client(
        http2=False,
        follow_redirects=False,
        timeout=30,
        headers=HEADERS,
    ) as client:
        # Establish CSRF session (needed for the callback to accept our request)
        _get_csrf_token(client)

        # Verify the OTP — Exa's custom endpoint validates the 6-digit code
        resp = client.post(
            f"{AUTH_BASE}/api/verify-otp",
            json={"email": email.lower(), "otp": code},
        )
        if resp.status_code != 200:
            error_msg = "Invalid or expired verification code"
            try:
                error_msg = resp.json().get("error", error_msg)
            except Exception:
                pass
            return {"__result__": {"error": error_msg}}

        data = resp.json()
        hashed_otp = data.get("hashedOtp", "")
        raw_otp = data.get("rawOtp", "")

        if not hashed_otp:
            return {"__result__": {"error": "Unexpected verify-otp response", "raw": data}}

        # Construct the token NextAuth expects: hashedOtp:rawOtp
        # NextAuth hashes this with SHA256+secret and compares to the DB entry.
        token = f"{hashed_otp}:{raw_otp}"
        callback_url = (
            f"{AUTH_BASE}/api/auth/callback/email"
            f"?email={urllib.parse.quote(email.lower())}"
            f"&token={urllib.parse.quote(token)}"
            f"&callbackUrl={urllib.parse.quote(CALLBACK_URL)}"
        )

        # Hit the NextAuth callback — this sets the session-token cookie
        resp2 = client.get(callback_url, follow_redirects=True)
        if resp2.status_code >= 400:
            return {"__result__": {"error": f"Callback failed: HTTP {resp2.status_code}"}}

    # Extract the session token
    session_token = None
    for cookie in client.cookies.jar:
        if cookie.name == "next-auth.session-token":
            session_token = cookie.value
            break

    if not session_token:
        return {"__result__": {"error": "Login succeeded but no session token received"}}

    # Validate session and store via __secrets__
    cookies = {"next-auth.session-token": session_token}
    with _make_dashboard_client(cookies) as dashboard:
        session = _check_session(dashboard)
        if not session:
            return {"__result__": {"error": "Session token invalid after login"}}

    return {
        "__secrets__": [{
            "issuer": "exa.ai",
            "identifier": email,
            "item_type": "cookie",
            "label": "Exa Dashboard Session",
            "source": "exa",
            "value": cookies,
            "metadata": {
                "masked": {"next-auth.session-token": "••••(JWT)"},
                "dashboard_url": DASHBOARD_BASE,
                "user_id": session["user"].get("id"),
                "team_id": session["user"].get("currentTeamId"),
            },
        }],
        "__result__": {
            "status": "authenticated",
            "email": email,
            "team": session["user"].get("currentTeamName", "unknown"),
            "user_id": session["user"].get("id"),
        },
    }


def store_session_cookies(*, email: str, session_token: str, cf_clearance: str = "", **params) -> dict:
    """Store browser-extracted session cookies for authenticated dashboard access.

    Fallback for when verify_login_code can't be used (e.g. Google SSO).
    Validates the session, then stores the cookies via __secrets__.
    """
    if not email or not session_token:
        return {"__result__": {"error": "email and session_token are required"}}

    cookies = {"next-auth.session-token": session_token}
    if cf_clearance:
        cookies["cf_clearance"] = cf_clearance

    with _make_dashboard_client(cookies) as client:
        session = _check_session(client)
        if not session:
            return {"__result__": {"error": "Session token invalid or expired"}}

    return {
        "__secrets__": [{
            "issuer": "exa.ai",
            "identifier": email,
            "item_type": "cookie",
            "label": "Exa Dashboard Session",
            "source": "exa",
            "value": cookies,
            "metadata": {
                "masked": {"next-auth.session-token": "••••(JWT)"},
                "dashboard_url": DASHBOARD_BASE,
                "user_id": session["user"].get("id"),
                "team_id": session["user"].get("currentTeamId"),
            },
        }],
        "__result__": {
            "status": "authenticated",
            "identifier": email,
            "issuer": "exa.ai",
            "user_id": session["user"].get("id"),
            "team": session["user"].get("teams", [{}])[0].get("name"),
        },
    }


def _parse_cookie_string(raw) -> dict:
    """Accept cookie header string or dict and return a {name: value} dict."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        pairs = {}
        for part in raw.split(";"):
            part = part.strip()
            if "=" in part:
                name, _, value = part.partition("=")
                pairs[name.strip()] = value.strip()
        return pairs
    return {}


def _make_dashboard_client(cookies) -> httpx.Client:
    """Create an httpx client for dashboard.exa.ai (Vercel-hosted).

    Uses http2=False because Vercel's Security Checkpoint blocks httpx's
    HTTP/2 JA4 fingerprint (429 regardless of cookies/headers). HTTP/1.1
    with a browser User-Agent passes cleanly.
    """
    return httpx.Client(
        http2=False,
        follow_redirects=True,
        timeout=30,
        headers=HEADERS,
        cookies=_parse_cookie_string(cookies),
    )


def _require_session(client: httpx.Client) -> dict:
    """Check session and raise on failure so the engine's cookie retry fires."""
    session = _check_session(client)
    if not session:
        raise Exception("Unauthorized (HTTP 403): Exa dashboard session expired or invalid")
    return session


def get_api_keys(*, cookies: dict = None, store: bool = True, **params) -> dict:
    """List API keys from the Exa dashboard and optionally store the first enabled key.

    The `id` field in the API response IS the full API key value (UUID format).
    The dashboard UI masks it, but the API returns it in full.

    If store=True (default), the first enabled key is stored via __secrets__
    so exa.search works immediately after.
    """
    if not cookies:
        return {"__result__": {"error": "No dashboard cookies — run send_login_code + store_session_cookies first"}}

    with _make_dashboard_client(cookies) as client:
        session = _require_session(client)
        email = session["user"]["email"]

        resp = client.get(f"{DASHBOARD_BASE}/api/get-api-keys")
        resp.raise_for_status()
        data = resp.json()

    keys = data.get("apiKeys", [])
    enabled_keys = [k for k in keys if k.get("enabled")]

    result = {
        "__result__": {
            "api_keys": [
                {
                    "name": k["name"],
                    "enabled": k["enabled"],
                    "created_at": k["createdAt"],
                    "rate_limit": k.get("rateLimit"),
                    "masked_key": k["id"][:6] + "••••••••",
                }
                for k in keys
            ],
            "count": len(keys),
        }
    }

    if store and enabled_keys:
        key = enabled_keys[0]
        result["__secrets__"] = [{
            "issuer": "exa.ai",
            "identifier": email,
            "item_type": "api_key",
            "label": f"Exa API Key ({key['name']})",
            "source": "exa",
            "value": {"key": key["id"]},
            "metadata": {
                "masked": {"key": key["id"][:6] + "••••••••"},
                "dashboard_url": f"{DASHBOARD_BASE}/api-keys",
                "key_name": key["name"],
            },
        }]

    return result


def get_teams(*, cookies: dict = None, **params) -> dict:
    """Get team info including rate limits, credits, and usage from the dashboard."""
    if not cookies:
        return {"__result__": {"error": "No dashboard cookies — run send_login_code + store_session_cookies first"}}

    with _make_dashboard_client(cookies) as client:
        _require_session(client)
        resp = client.get(f"{DASHBOARD_BASE}/api/get-teams")
        resp.raise_for_status()
        data = resp.json()

    teams = data.get("teams", [])
    return {
        "__result__": {
            "teams": [
                {
                    "id": t["id"],
                    "name": t["name"],
                    "role": t.get("role"),
                    "rate_limit": t.get("customRateLimit"),
                    "max_results": t.get("customNumResults"),
                    "credits_cents": t.get("totalAppliedCreditsCents"),
                    "usage_limit": t.get("usageLimit"),
                    "monthly_usage": t.get("monthlyUsage"),
                    "is_enterprise": t.get("isEnterprise"),
                    "users": [
                        {"email": u["email"], "role": u["role"]}
                        for u in t.get("users", [])
                    ],
                }
                for t in teams
            ],
            "count": len(teams),
        }
    }


def create_api_key(*, cookies: dict = None, name: str = "agentOS", **params) -> dict:
    """Create a new API key on the Exa dashboard and store it via __secrets__."""
    if not cookies:
        return {"__result__": {"error": "No dashboard cookies — run send_login_code + store_session_cookies first"}}

    with _make_dashboard_client(cookies) as client:
        session = _require_session(client)
        email = session["user"]["email"]

        resp = client.post(
            f"{DASHBOARD_BASE}/api/create-api-key",
            json={"name": name},
        )
        resp.raise_for_status()
        data = resp.json()

    key_obj = data.get("apiKey") or {}
    api_key = key_obj.get("id") if isinstance(key_obj, dict) else key_obj
    if not api_key or not isinstance(api_key, str):
        return {"__result__": {"error": "API key not found in creation response", "raw": data}}

    masked = api_key[:6] + "••••" + api_key[-4:]
    return {
        "__secrets__": [{
            "issuer": "exa.ai",
            "identifier": email or "unknown",
            "item_type": "api_key",
            "label": f"Exa API Key ({name})",
            "source": "exa",
            "value": {"key": api_key},
            "metadata": {
                "masked": {"key": masked},
                "dashboard_url": f"{DASHBOARD_BASE}/api-keys",
                "key_name": name,
            },
        }],
        "__result__": {
            "status": "created",
            "key_name": name,
            "issuer": "exa.ai",
            "masked_key": masked,
        },
    }


def logout(*, cookies: dict = None, **params) -> dict:
    """Sign out of the Exa dashboard and invalidate the session.

    Hits NextAuth's signout endpoint to invalidate the server-side session,
    then returns a signal to clear the stored credentials.
    """
    if not cookies:
        return {"__result__": {"status": "already_logged_out"}}

    with _make_dashboard_client(cookies) as client:
        csrf_token = _get_csrf_token(client)
        resp = client.post(
            f"{AUTH_BASE}/api/auth/signout",
            data={"csrfToken": csrf_token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    return {
        "__result__": {
            "status": "logged_out",
            "hint": "Dashboard session invalidated. Stored cookies should be cleared.",
        }
    }
