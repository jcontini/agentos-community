"""
exa.py — Dashboard auth and API key management for Exa

Auth architecture (discovered via Playwright reverse engineering):
  - Auth domain:      auth.exa.ai (NextAuth.js / Auth.js)
  - Dashboard domain: dashboard.exa.ai
  - Login method:     Email verification code (6-digit, NOT a magic link)
  - Session:          JWT in `next-auth.session-token` cookie (.exa.ai)
  - Protection:       Cloudflare cf_clearance on .exa.ai

Login flow (agent-orchestrated, Playwright for code submission):
  1. send_login_code(email)    [HTTPX]
     - GET  auth.exa.ai/api/auth/csrf       → CSRF token + cookie
     - POST auth.exa.ai/api/auth/signin/email → triggers verification code email

  2. Agent retrieves 6-digit code from email (any provider)

  3. Code submission              [Playwright required]
     - The auth page submits the code via a native HTML form POST that
       Exa's custom NextAuth handles server-side. HTTPX cannot replay this
       (tested: both GET and POST to /api/auth/callback/email fail with
       ?error=Verification or ?error=configuration).
     - The agent uses Playwright: type code into input, click submit,
       then extract cookies from the browser.

  4. store_session_cookies(cookies)   [HTTPX]
     - Validates session via /api/auth/session
     - Stores cookies via __secrets__

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

    This is the HTTPX-compatible part of the login flow. After calling this,
    the agent must:
      1. Check the user's email for the 6-digit code
      2. Use Playwright to enter the code on the auth page and complete login
      3. Extract browser cookies and call store_session_cookies

    The auth page's code submission uses a native HTML form POST that HTTPX
    cannot replay — Playwright is required for that step.
    """
    if not email:
        return {"__result__": {"error": "email is required"}}

    with httpx.Client(
        http2=True,
        follow_redirects=True,
        timeout=30,
        headers=HEADERS,
    ) as client:
        csrf_token = _get_csrf_token(client)
        _send_verification_email(client, csrf_token, email)

    return {
        "__result__": {
            "status": "code_sent",
            "email": email,
            "hint": (
                "A 6-digit code was sent to the email. To complete login:\n"
                "1. Search email for subject 'Sign in to Exa Dashboard' from exa.ai\n"
                "2. Extract the 6-digit code\n"
                "3. Use Playwright to navigate to https://dashboard.exa.ai (redirects to auth)\n"
                "4. Type the email, submit, then type the code and submit\n"
                "5. Extract cookies with: playwright.cookies({ domain: '.exa.ai' })\n"
                "6. Call exa.store_session_cookies with the next-auth.session-token and cf_clearance cookies"
            ),
        }
    }


def store_session_cookies(*, email: str, session_token: str, cf_clearance: str = "", **params) -> dict:
    """Store browser-extracted session cookies for authenticated dashboard access.

    Called after Playwright login. Validates the session, then stores the
    cookies via __secrets__ so get_api_keys and other dashboard operations work.
    """
    if not email or not session_token:
        return {"__result__": {"error": "email and session_token are required"}}

    cookies = {"next-auth.session-token": session_token}
    if cf_clearance:
        cookies["cf_clearance"] = cf_clearance

    with httpx.Client(
        http2=True,
        follow_redirects=True,
        timeout=30,
        headers=HEADERS,
        cookies=cookies,
    ) as client:
        session = _check_session(client)
        if not session:
            return {"__result__": {"error": "Session token invalid or expired"}}

    return {
        "__secrets__": [{
            "issuer": "dashboard.exa.ai",
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
            "issuer": "dashboard.exa.ai",
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
    """Create an HTTPX client with dashboard auth cookies."""
    return httpx.Client(
        http2=True,
        follow_redirects=True,
        timeout=30,
        headers=HEADERS,
        cookies=_parse_cookie_string(cookies),
    )


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
        session = _check_session(client)
        if not session:
            return {"__result__": {"error": "Dashboard session expired — re-authenticate"}}
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
            "issuer": "api.exa.ai",
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
        session = _check_session(client)
        email = session["user"]["email"] if session else "unknown"

        resp = client.post(
            f"{DASHBOARD_BASE}/api/create-api-key",
            json={"name": name},
        )
        resp.raise_for_status()
        data = resp.json()

    api_key = data.get("apiKey") or data.get("key") or data.get("secret")
    if not api_key:
        return {"__result__": {"error": "API key not found in creation response", "raw": data}}

    return {
        "__secrets__": [{
            "issuer": "api.exa.ai",
            "identifier": email or "unknown",
            "item_type": "api_key",
            "label": f"Exa API Key ({name})",
            "source": "exa",
            "value": {"key": api_key},
            "metadata": {
                "masked": {"key": "••••" + api_key[-4:]},
                "dashboard_url": f"{DASHBOARD_BASE}/api-keys",
                "key_name": name,
            },
        }],
        "__result__": {
            "status": "created",
            "key_name": name,
            "issuer": "api.exa.ai",
            "masked_key": "••••" + api_key[-4:],
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
