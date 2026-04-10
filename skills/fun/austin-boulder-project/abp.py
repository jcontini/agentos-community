"""
Austin Boulder Project — Tilefive Portal API

Reverse-engineered Python functions for authenticating and booking classes.
Build incrementally: each function proves one piece of the API contract.

Platform: Tilefive (approach.app)
Portal:   https://boulderingproject.portal.approach.app
Auth:     AWS Cognito (us-east-1) via USER_PASSWORD_AUTH
"""

import asyncio
import re
from agentos import http, returns

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NAMESPACE = "boulderingproject"
PORTAL_ORIGIN = "https://boulderingproject.portal.approach.app"
PORTAL_API = "https://portal.api.prod.tilefive.com"
WIDGETS_API = "https://widgets.api.prod.tilefive.com"
COGNITO_REGION = "us-east-1"
COGNITO_ENDPOINT = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/"

# Fallback config — extracted from the app bundle (see _discover_config()).
# These rotate when Tilefive redeploys; _discover_config() fetches fresh values.
# Format reference: widgetsApiKey ~40 chars, userPoolId "us-east-1_XXXXXXXX"
FALLBACK_WIDGETS_API_KEY    = "OQ2z4Q3jSU1BW3y9dyfEW5FlEFu1ozIj7jE27qjy"
FALLBACK_COGNITO_POOL_ID    = "us-east-1_x871NwuXM"
FALLBACK_COGNITO_CLIENT_ID  = "jikhc095m6r9olu8rudg4gh5d"

# Runtime cache for discovered config (avoids re-fetching the bundle every call)
_CONFIG_CACHE: dict | None = None

# Regex patterns for bundle extraction (see requirements.md for full context)
_RE_BUNDLE_URL      = re.compile(r'src="/assets/(app-[a-zA-Z0-9]+\.js)"')
_RE_WIDGETS_KEY     = re.compile(r'widgetsApiKey:\{"us-east-1":"([^"]{30,})"')
_RE_POOL_ID         = re.compile(r'userPoolId:"(us-east-1_[A-Za-z0-9]+)"')
_RE_CLIENT_ID       = re.compile(r'userPoolClientId:"([A-Za-z0-9]{20,60})"')

# Austin Springdale — primary target location
AUSTIN_SPRINGDALE = {
    "id": 6,
    "uuid": "bd3709e9-a27c-11ed-ae87-0a21e3900363",
    "name": "Austin Springdale",
    "timezone": "America/Chicago",
}

AUSTIN_WESTGATE = {
    "id": 5,
    "uuid": "b859f96e-a27c-11ed-ae87-0a21e3900363",
    "name": "Austin Westgate",
    "timezone": "America/Chicago",
}


# ---------------------------------------------------------------------------
# Step 1: Discover the Cognito config from the portal
# ---------------------------------------------------------------------------

async def _get_region() -> str:
    """
    GET /region?namespace=boulderingproject
    Returns the AWS region for Cognito auth.
    Confirmed working without auth or API key.
    """
    data = await _request(f"{PORTAL_API}/region", params={"namespace": NAMESPACE})
    return data["DEFAULT_REGION"]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

async def _request(
    url: str,
    *,
    headers: dict | None = None,
    params: dict | None = None,
    json_body: dict | None = None,
    method: str | None = None,
) -> dict | str:
    """
    Dispatch an HTTP request through the SDK with retry on transient errors.

    http.headers(accept="json") provides browser-like Sec-CH-UA + Sec-Fetch headers
    needed to pass CloudFront WAF JA4 fingerprinting.

    Returns the parsed JSON body when the response is application/json, otherwise
    the raw text body. Raises RuntimeError on non-retryable 4xx or exhausted retries.
    """
    if method is None:
        method = "POST" if json_body is not None else "GET"
    verb = method.upper()
    call = {
        "GET":    http.get,
        "POST":   http.post,
        "DELETE": http.delete,
        "PATCH":  http.patch,
        "PUT":    http.put,
    }.get(verb)
    if call is None:
        raise ValueError(f"unsupported HTTP method: {method}")

    last_err: Exception | None = None
    for attempt in range(3):
        try:
            kwargs = dict(http.headers(accept="json", extra=headers))
            if params is not None:
                kwargs["params"] = params
            if json_body is not None:
                kwargs["json"] = json_body
            resp = await call(url, **kwargs)
            status = resp["status"]
            if status >= 400:
                if status not in {429, 500, 502, 503, 504} or attempt == 2:
                    body_preview = resp.get("body", "")
                    if isinstance(body_preview, (bytes, bytearray)):
                        body_preview = body_preview.decode("utf-8", errors="replace")
                    raise RuntimeError(f"HTTP {status} for {verb} {url}: {body_preview[:200]}")
                last_err = RuntimeError(f"HTTP {status}")
            else:
                return resp["json"] if resp.get("json") is not None else resp.get("body", "")
        except RuntimeError:
            raise
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt == 2:
                raise
        await asyncio.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Request failed: {last_err}")


# ---------------------------------------------------------------------------
# Config discovery
# ---------------------------------------------------------------------------

async def _discover_config(force: bool = False) -> dict:
    """
    Extract live config from the Tilefive app bundle.

    What it finds:
      - widgetsApiKey  (X-Api-Key header for widgets.api.prod.tilefive.com)
      - cognitoPoolId  (AWS Cognito UserPoolId)
      - cognitoClientId (AWS Cognito app client ID)

    How it works:
      1. Fetch the portal HTML → find the bundle URL (app-HASH.js)
      2. Fetch the bundle → regex-extract the three values
      3. Cache result in-process; return fallbacks on any failure

    The bundle is served same-origin by Tilefive's CDN and may refuse direct
    fetches from outside a browser context. If step 2 fails, fallback constants
    are returned (see FALLBACK_* at the top of this file). They're good until
    Tilefive redeploys with new keys.

    See requirements.md → "CORS / API Key" for the full extraction rationale.
    """
    global _CONFIG_CACHE
    if _CONFIG_CACHE and not force:
        return _CONFIG_CACHE

    fallback = {
        "widgetsApiKey":   FALLBACK_WIDGETS_API_KEY,
        "cognitoPoolId":   FALLBACK_COGNITO_POOL_ID,
        "cognitoClientId": FALLBACK_COGNITO_CLIENT_ID,
    }

    try:
        # Step 1: get the portal HTML and find the bundle filename
        html = await _request(PORTAL_ORIGIN)
        if isinstance(html, (bytes, bytearray)):
            html = html.decode("utf-8", errors="replace")
        m = _RE_BUNDLE_URL.search(html or "")
        if not m:
            return fallback
        bundle_url = f"{PORTAL_ORIGIN}/assets/{m.group(1)}"

        # Step 2: fetch the bundle (may fail if CDN blocks non-browser origin)
        bundle = await _request(bundle_url, headers={
            "Referer": f"{PORTAL_ORIGIN}/",
            "Origin": PORTAL_ORIGIN,
        })
        if isinstance(bundle, (bytes, bytearray)):
            bundle = bundle.decode("utf-8", errors="replace")
        if not isinstance(bundle, str):
            return fallback

        # If the CDN returned HTML instead of JS, fall back
        if bundle.lstrip().startswith("<!"):
            return fallback

        config = dict(fallback)
        if km := _RE_WIDGETS_KEY.search(bundle):
            config["widgetsApiKey"] = km.group(1)
        if pm := _RE_POOL_ID.search(bundle):
            config["cognitoPoolId"] = pm.group(1)
        if cm := _RE_CLIENT_ID.search(bundle):
            config["cognitoClientId"] = cm.group(1)

        _CONFIG_CACHE = config
        return config

    except Exception:
        return fallback


async def _widgets_headers(access_token: str | None = None) -> dict:
    """
    Headers required for all widgets.api.prod.tilefive.com calls.

    Authorization is NOT a JWT — it's the namespace/tenant ID extracted from
    the portal subdomain: window.location.host.split(".")[0] → "boulderingproject"
    The API Gateway uses this for tenant routing. When a user IS logged in,
    the authenticated portal API (Ie()) uses a real Cognito IdToken instead.
    """
    cfg = await _discover_config()
    headers = {
        "X-Api-Key": cfg["widgetsApiKey"],   # casing from bundle: "X-Api-Key"
        "Authorization": access_token or NAMESPACE,  # namespace when unauthenticated
        "Origin": PORTAL_ORIGIN,
        "Referer": f"{PORTAL_ORIGIN}/",
    }
    return headers


async def _get_locations() -> list[dict]:
    """
    GET https://widgets.api.prod.tilefive.com/locations
    Returns all Bouldering Project locations.
    Requires X-Api-Key + Authorization: namespace (see _widgets_headers()).
    """
    return await _request(f"{WIDGETS_API}/locations", headers=await _widgets_headers())


async def _get_location_settings(location_id: int) -> dict:
    """
    GET https://widgets.api.prod.tilefive.com/locationsettings/{locationId}/portal
    Returns portal config for a location.
    Example for Austin Springdale (id=6):
      { locationId: 6, setting: { membershipTypeIds: [418], passTypeIds: [307], ... } }
    """
    url = f"{WIDGETS_API}/locationsettings/{location_id}/portal"
    return await _request(url, headers=await _widgets_headers())


async def _get_activities() -> list[dict]:
    """
    GET https://widgets.api.prod.tilefive.com/activities
    Returns all activity categories.
    Key IDs: 4=Climbing Classes, 5=Yoga, 6=Fitness
    """
    data = await _request(f"{WIDGETS_API}/activities", headers=await _widgets_headers())
    return data.get("data", [])


async def _get_schedule(
    location_id: int = AUSTIN_SPRINGDALE["id"],
    activity_ids: list[int] = None,
    date: str = None,
) -> dict:
    """
    GET https://widgets.api.prod.tilefive.com/cal
    Fetch the class schedule — NO AUTH REQUIRED.

    Args:
      location_id:  e.g. 6 for Austin Springdale
      activity_ids: e.g. [4, 5, 6] for Climbing, Yoga, Fitness (default)
      date:         YYYY-MM-DD (default: today in Austin timezone)

    Returns dict with:
      bookings:   list of BookingInstance (each class occurrence)
      calEvents:  list (usually empty)
      pagination: { page, pageCount, pageSize, rowCount }

    BookingInstance key fields:
      id                  — booking instance ID (use this to register)
      name                — e.g. "Flow w/Todd C"
      startDT / endDT     — ISO8601 UTC
      occurrenceDate      — YYYY-MM-DD local
      status              — "active" | "cancelled"
      ticketsRemaining    — spots left (0 = full, None = unlimited)
      event.maxCustomers  — total capacity
      event.entranceRequirement — "MP" = membership/pass required
    """
    from datetime import datetime, timezone, timedelta

    if activity_ids is None:
        activity_ids = [4, 5, 6]

    if date is None:
        # Austin is UTC-5/UTC-6; use today in US/Central
        now_utc = datetime.now(timezone.utc)
        cst_offset = timedelta(hours=-6)
        today_cst = (now_utc + cst_offset).date()
        date = today_cst.isoformat()

    # Day window: midnight CST = UTC+5h or +6h depending on DST
    # Use simple approach: midnight-to-midnight UTC offset for CST (-6h)
    start_dt = f"{date}T06:00:00.000Z"   # midnight CST = 06:00 UTC (CDT) or 05:00 UTC (CST)
    end_dt   = f"{date}T05:59:59.999Z"   # end of next day... approximation; use cal's own range

    # Better: just pass the date range the embed uses (05:00Z start = midnight CST-ish)
    start_dt = f"{date}T05:00:00.000Z"
    # end = next calendar day 04:59:59
    from datetime import date as date_type
    d = date_type.fromisoformat(date)
    next_day = (d + timedelta(days=1)).isoformat()
    end_dt = f"{next_day}T04:59:59.999Z"

    return await _request(
        f"{WIDGETS_API}/cal",
        headers=await _widgets_headers(),
        params={
            "startDT": start_dt,
            "endDT": end_dt,
            "locationId": location_id,
            "activityId": ",".join(str(i) for i in activity_ids),
            "page": 1,
            "pageSize": 50,
        },
    )


# ---------------------------------------------------------------------------
# Step 2: Authenticate via AWS Cognito
# ---------------------------------------------------------------------------

async def _login(email: str, password: str) -> dict:
    """
    Authenticate against AWS Cognito using USER_PASSWORD_AUTH flow.
    ClientId is auto-discovered from the app bundle via _discover_config().

    Returns the AuthenticationResult dict with:
      - AccessToken  (use for API calls, expires in 1hr)
      - IdToken      (JWT with user claims)
      - RefreshToken (long-lived; use with _refresh_tokens() to avoid re-login)

    Cognito endpoint:
      POST https://cognito-idp.us-east-1.amazonaws.com/
      X-Amz-Target: AWSCognitoIdentityProviderService.InitiateAuth

    Header override trick: Cognito rejects application/json — it wants
    application/x-amz-json-1.1. The engine's per-request headers override
    the body-implied Content-Type, so json=dict + headers={"Content-Type":
    "application/x-amz-json-1.1"} works.
    """
    cfg = await _discover_config()
    headers = {
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
    }
    body = {
        "AuthFlow": "USER_PASSWORD_AUTH",
        "ClientId": cfg["cognitoClientId"],
        "AuthParameters": {"USERNAME": email, "PASSWORD": password},
    }
    result = await _request(COGNITO_ENDPOINT, headers=headers, json_body=body)
    return result["AuthenticationResult"]


async def _refresh_tokens(refresh_token: str) -> dict:
    """
    Get a fresh AccessToken using a stored RefreshToken (no re-login needed).
    AccessToken TTL is 1hr; RefreshToken is long-lived.
    """
    cfg = await _discover_config()
    headers = {
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
    }
    body = {
        "AuthFlow": "REFRESH_TOKEN_AUTH",
        "ClientId": cfg["cognitoClientId"],
        "AuthParameters": {"REFRESH_TOKEN": refresh_token},
    }
    result = await _request(COGNITO_ENDPOINT, headers=headers, json_body=body)
    return result["AuthenticationResult"]


# ---------------------------------------------------------------------------
# Step 4: Book a class (TODO — discover endpoint post-login)
# ---------------------------------------------------------------------------

def _portal_headers(id_token: str) -> dict:
    """
    Headers for authenticated portal.api.prod.tilefive.com calls (Ie() client).

    Uses the Cognito IdToken directly as Authorization (not "Bearer <token>").
    Confirmed from bundle: bI=async()=>(await zE()).tokens?.idToken
    and Ie() sets headers: { Authorization: idToken }
    """
    return {
        "Authorization": id_token,
        "Content-Type": "application/json",
        "Origin": PORTAL_ORIGIN,
        "Referer": f"{PORTAL_ORIGIN}/",
    }


async def _get_my_bookings(id_token: str) -> list[dict]:
    """
    GET https://portal.api.prod.tilefive.com/customers/bookings (inferred)
    Returns the authenticated user's upcoming bookings.
    Requires Cognito IdToken from _login().
    TODO: confirm exact path via network capture after login.
    """
    url = f"{PORTAL_API}/customers/bookings"
    return await _request(url, headers=_portal_headers(id_token))


async def _book_class(id_token: str, booking_instance_id: int, num_guests: int = 0) -> dict:
    """
    Book a class (add the authenticated user to a booking instance).

    Discovered from bundle:
      ete=(e,t) => Ie().then(a => a.post(`/bookings/${e}/customers`, t))
      Ie() uses Authorization: idToken (Cognito IdToken, NOT AccessToken)

    Args:
      id_token:            Cognito IdToken from _login() → auth["IdToken"]
      booking_instance_id: The `id` field from _get_schedule() bookings
      num_guests:          Number of additional guests (0 = just yourself)

    Returns the API response (created reservation object).

    Note: body payload needs confirmation via live network capture.
    Classes with entranceRequirement="MP" require an active membership or pass.
    """
    url = f"{PORTAL_API}/bookings/{booking_instance_id}/customers"
    return await _request(url, headers=_portal_headers(id_token), json_body={"numGuests": num_guests})


async def _cancel_booking(id_token: str, booking_instance_id: int, reservation_id: int) -> dict:
    """
    Cancel a booking reservation.

    Discovered from bundle:
      tte=(e,t) => Ie().then(a => a.delete(`/bookings/${e}/reservations/${t}`))

    Args:
      id_token:            Cognito IdToken
      booking_instance_id: The booking instance id
      reservation_id:      The reservation id returned by _book_class()
    """
    url = f"{PORTAL_API}/bookings/{booking_instance_id}/reservations/{reservation_id}"
    return await _request(url, headers=_portal_headers(id_token), method="DELETE")


async def _get_my_memberships(id_token: str) -> list[dict]:
    """
    GET https://portal.api.prod.tilefive.com/customers/memberships
    Returns the user's active memberships.
    From bundle: Qee=()=>Ie().then(e=>e.get("/customers/memberships"))
    """
    url = f"{PORTAL_API}/customers/memberships"
    return await _request(url, headers=_portal_headers(id_token))


async def _get_my_passes(id_token: str) -> list[dict]:
    """
    GET https://portal.api.prod.tilefive.com/customers/passes
    Returns the user's active class passes.
    From bundle: Jee=()=>Ie().then(e=>e.get("/customers/passes"))
    """
    url = f"{PORTAL_API}/customers/passes"
    return await _request(url, headers=_portal_headers(id_token))


# ---------------------------------------------------------------------------
# Entity helpers
# ---------------------------------------------------------------------------

def _booking_to_entity(b: dict) -> dict:
    """Normalise a BookingInstance from /cal into the agentOS class entity shape."""
    event = b.get("event", {})
    activities = event.get("activitys") or []
    activity_name = activities[0].get("name", "") if activities else ""
    spots = b.get("ticketsRemaining")
    capacity = event.get("maxCustomers")
    full = spots == 0
    desc_parts = []
    if activity_name:
        desc_parts.append(activity_name)
    if full:
        desc_parts.append("FULL")
    elif spots is not None:
        desc_parts.append(f"{spots}/{capacity} spots")
    return {
        "id": b["id"],
        "name": b["name"],
        "content": " — ".join(desc_parts),
        "startDT": b["startDT"],
        "endDT": b["endDT"],
        "activityType": activity_name,
        "capacity": capacity,
        "spotsRemaining": spots,
        "isFull": full,
    }


async def _get_id_token(credentials: str) -> str:
    """Login with 'email:password' string and return the Cognito IdToken."""
    if not credentials or ":" not in credentials:
        raise ValueError(
            "Credentials must be in 'email:password' format. "
            "Add them in agentOS skill settings for austin-boulder-project."
        )
    email, password = credentials.split(":", 1)
    auth = await _login(email.strip(), password.strip())
    return auth["IdToken"]


# ---------------------------------------------------------------------------
# Operation entrypoints — called by the python: executor with kwargs
# ---------------------------------------------------------------------------

@returns("class[]")
async def op_get_schedule(
    location_id: int = AUSTIN_SPRINGDALE["id"],
    activity_ids: str = None,
    date: str = None,
    **params,
) -> list[dict]:
    """Get today's class schedule as entity-shaped dicts."""
    if isinstance(activity_ids, str):
        parsed_ids = [int(x.strip()) for x in activity_ids.split(",") if x.strip()]
    elif isinstance(activity_ids, list):
        parsed_ids = [int(x) for x in activity_ids]
    else:
        parsed_ids = [4, 5, 6]
    result = await _get_schedule(
        location_id=int(location_id),
        activity_ids=parsed_ids,
        date=date or None,
    )
    return [_booking_to_entity(b) for b in result.get("bookings", [])]


@returns({"ok": "boolean", "message": "string"})
async def op_book_class(
    booking_instance_id: int,
    num_guests: int = 0,
    **params,
) -> dict:
    """Book a class using stored credentials."""
    credentials = params.get("auth", {}).get("key", "")
    id_token = await _get_id_token(credentials)
    result = await _book_class(id_token, int(booking_instance_id), num_guests=int(num_guests))
    return {"ok": True, "message": "Booked successfully", "result": result}


@returns({"ok": "boolean", "message": "string"})
async def op_cancel_booking(
    booking_instance_id: int,
    reservation_id: int,
    **params,
) -> dict:
    """Cancel a class reservation."""
    credentials = params.get("auth", {}).get("key", "")
    id_token = await _get_id_token(credentials)
    result = await _cancel_booking(id_token, int(booking_instance_id), int(reservation_id))
    return {"ok": True, "message": "Cancelled successfully", "result": result}


@returns({"items": "array"})
async def op_get_my_memberships(**params) -> list[dict]:
    """List active memberships for the logged-in account."""
    credentials = params.get("auth", {}).get("key", "")
    id_token = await _get_id_token(credentials)
    return await _get_my_memberships(id_token)


@returns({"items": "array"})
async def op_get_my_passes(**params) -> list[dict]:
    """List active class passes for the logged-in account."""
    credentials = params.get("auth", {}).get("key", "")
    id_token = await _get_id_token(credentials)
    return await _get_my_passes(id_token)
