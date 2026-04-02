"""Uber skill — rides (GraphQL) and Eats (RPC) via browser session cookies."""

import json as _json
import uuid as uuid_mod
from agentos import http, get_cookies, require_cookies

# ---------------------------------------------------------------------------
# Rides API — GraphQL at riders.uber.com
# ---------------------------------------------------------------------------

GRAPHQL_URL = "https://riders.uber.com/graphql"

# Rides-specific headers merged via http.headers(extra=...).
# ALWAYS use http.headers() for the base — it provides browser-grade UA, sec-ch-*,
# and Sec-Fetch-* headers. Without these, some endpoints return 500.
# See agentos-community/docs/skills/sdk.md for http.headers() docs.
RIDES_EXTRA_HEADERS = {
    "x-csrf-token": "x",
    "x-uber-rv-session-type": "desktop_session",
}

# ---------------------------------------------------------------------------
# Eats API — RPC at www.ubereats.com/_p/api/
# Completely separate from rides: different domain, different auth, different protocol.
# Auth: .ubereats.com cookies (via "eats" connection in skill.yaml)
# Required header: x-csrf-token: x (literal string, same as rides)
# ---------------------------------------------------------------------------

EATS_API_BASE = "https://www.ubereats.com/_p/api"

# Eats headers: x-csrf-token is required. Other browser headers (UA, sec-ch-*)
# are needed for some endpoints (e.g. getReceiptByWorkflowUuidV1 returns 500 without them).
# Use http.headers(waf="cf", accept="json") to get proper browser headers,
# then merge Eats-specific headers via extra=.
# See agentos-community/docs/skills/sdk.md for http.headers() docs.
EATS_EXTRA_HEADERS = {
    "x-csrf-token": "x",
}

# ---------------------------------------------------------------------------
# GraphQL queries
# ---------------------------------------------------------------------------

CURRENT_USER_QUERY = """
query CurrentUserRidersWeb {
  currentUser {
    firstName
    lastName
    email
    formattedNumber
    pictureUrl
    rating
    tenancy
    uuid
    role
    signupCountry
    userTags {
      hasDelegate
      isAdmin
      isTester
      isTeen
      __typename
    }
    paymentProfiles {
      authenticationType
      displayable {
        displayName
        iconURL
        __typename
      }
      hasBalance
      tokenType
      uuid
      __typename
    }
    profiles {
      defaultPaymentProfileUuid
      name
      type
      uuid
      __typename
    }
    membershipBenefits {
      hasUberOne
      __typename
    }
    __typename
  }
}
"""

ACTIVITIES_QUERY = """
query Activities($cityID: Int, $endTimeMs: Float, $includePast: Boolean = true, $includeUpcoming: Boolean = true, $limit: Int = 5, $nextPageToken: String, $orderTypes: [RVWebCommonActivityOrderType!] = [RIDES, TRAVEL], $profileType: RVWebCommonActivityProfileType = PERSONAL, $startTimeMs: Float) {
  activities(cityID: $cityID) {
    cityID
    past(
      endTimeMs: $endTimeMs
      limit: $limit
      nextPageToken: $nextPageToken
      orderTypes: $orderTypes
      profileType: $profileType
      startTimeMs: $startTimeMs
    ) @include(if: $includePast) {
      activities {
        ...RVWebCommonActivityFragment
        __typename
      }
      nextPageToken
      __typename
    }
    upcoming @include(if: $includeUpcoming) {
      activities {
        ...RVWebCommonActivityFragment
        __typename
      }
      __typename
    }
    __typename
  }
}

fragment RVWebCommonActivityFragment on RVWebCommonActivity {
  buttons {
    isDefault
    startEnhancerIcon
    text
    url
    __typename
  }
  cardURL
  description
  imageURL {
    light
    dark
    __typename
  }
  subtitle
  title
  uuid
  __typename
}
"""

GET_TRIP_QUERY = """
query GetTrip($tripUUID: String!) {
  getTrip(tripUUID: $tripUUID) {
    trip {
      beginTripTime
      cityID
      countryID
      disableCanceling
      disableRating
      disableResendReceipt
      driver
      dropoffTime
      fare
      guest
      isRidepoolTrip
      isScheduledRide
      isSurgeTrip
      isUberReserve
      jobUUID
      marketplace
      paymentProfileUUID
      showRating
      status
      uuid
      vehicleDisplayName
      vehicleViewID
      waypoints
      __typename
    }
    mapURL
    polandTaxiLicense
    rating
    reviewer
    receipt {
      carYear
      distance
      distanceLabel
      duration
      vehicleType
      __typename
    }
    concierge {
      sourceType
      __typename
    }
    organization {
      name
      __typename
    }
    __typename
  }
}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gql(cookie_header: str, operation_name: str, query: str, variables: dict | None = None) -> dict:
    """Execute a GraphQL query against riders.uber.com.

    Uses http.headers() for browser-grade headers — we're acting as Brave,
    so we should always send what Brave sends. See docs/skills/sdk.md.
    """
    resp = http.post(
        GRAPHQL_URL,
        cookies=cookie_header,
        json={
            "operationName": operation_name,
            "query": query,
            "variables": variables or {},
        },
        **http.headers(waf="cf", accept="json", extra=RIDES_EXTRA_HEADERS),
    )

    status = resp.get("status") or 0
    body_str = resp.get("body") or ""
    url_final = resp.get("url") or ""
    if status != 200:
        if "auth.uber.com" in body_str or "auth.uber.com" in url_final:
            raise RuntimeError("SESSION_EXPIRED: Uber redirected to login — cookies expired.")
        raise RuntimeError(f"Uber GraphQL HTTP {status} url={url_final} ct={resp.get('content_type','')} body={body_str[:200]}")
    body = resp.get("json")
    if not body or not isinstance(body, dict):
        raise RuntimeError(f"Uber GraphQL returned non-JSON: status={status} ct={resp.get('content_type','')} len={len(body_str)} body={body_str[:300]}")
    if body.get("errors"):
        raise RuntimeError(f"Uber GraphQL error: {body['errors']}")
    return body.get("data", {})


def _is_login_redirect(resp: dict) -> bool:
    url = str(resp.get("url", ""))
    return "auth.uber.com" in url or "/v2/?" in url


from price_parser import Price

# Common Uber currency symbols → ISO 4217. price-parser extracts the symbol/code
# from fare strings; we resolve ambiguous symbols (like "$") using this map.
# Uber always prefixes with ISO codes for non-$ currencies (ZAR, TRY, CAD uses CA$),
# so the ambiguity is mostly theoretical — "$" is USD in Uber's context.
_SYMBOL_TO_ISO = {
    "$": "USD", "£": "GBP", "€": "EUR", "¥": "JPY",
    "₹": "INR", "R$": "BRL", "A$": "AUD", "C$": "CAD",
    "CA$": "CAD", "NZ$": "NZD", "HK$": "HKD", "S$": "SGD",
}


def _parse_fare(fare_str: str) -> tuple[float | None, str | None]:
    """Parse a fare string like '$16.37', 'ZAR 303.00', '£12.50' into (amount, currency_code).

    Uses price-parser for extraction. Returns (None, None) if unparseable.
    """
    if not fare_str:
        return None, None
    p = Price.fromstring(fare_str)
    amount = float(p.amount) if p.amount is not None else None
    currency = p.currency
    if currency and len(currency) == 3 and currency.isupper():
        return amount, currency  # already ISO code (ZAR, TRY, etc.)
    return amount, _SYMBOL_TO_ISO.get(currency) if currency else None


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

def check_session(**params) -> dict:
    """Validate session and return account identity."""
    cookie_header = get_cookies(params)
    if not cookie_header:
        return {"authenticated": False, "error": "no cookies"}

    try:
        data = _gql(cookie_header, "CurrentUserRidersWeb", CURRENT_USER_QUERY)
    except RuntimeError as e:
        return {"authenticated": False, "error": str(e)}

    user = data.get("currentUser")
    if not user:
        return {"authenticated": False, "error": "no user data"}

    return {
        "authenticated": True,
        "domain": "uber.com",
        "identifier": user.get("email") or user.get("uuid"),
        "display": f"{user.get('firstName', '')} {user.get('lastName', '')}".strip(),
    }


def whoami(**params) -> dict:
    """Get current user profile with full details."""
    cookie_header = require_cookies(params, "whoami")

    data = _gql(cookie_header, "CurrentUserRidersWeb", CURRENT_USER_QUERY)

    user = data.get("currentUser", {})
    benefits = user.get("membershipBenefits") or {}
    payment_profiles = user.get("paymentProfiles") or []

    return {
        "uuid": user.get("uuid"),
        "first_name": user.get("firstName"),
        "last_name": user.get("lastName"),
        "email": user.get("email"),
        "phone": user.get("formattedNumber"),
        "rating": user.get("rating"),
        "picture_url": user.get("pictureUrl"),
        "has_uber_one": benefits.get("hasUberOne", False),
        "signup_country": user.get("signupCountry"),
        "payment_methods": [
            {
                "name": (p.get("displayable") or {}).get("displayName"),
                "type": p.get("tokenType"),
                "uuid": p.get("uuid"),
            }
            for p in payment_profiles
        ],
        "profiles": [
            {"name": p.get("name"), "type": p.get("type"), "uuid": p.get("uuid")}
            for p in (user.get("profiles") or [])
        ],
    }


def list_trips(
    limit: int = 10,
    next_page_token: str | None = None,
    profile_type: str = "PERSONAL",
    order_types: str = "RIDES,TRAVEL",
    **params,
) -> list:
    """List past trips.

    Returns: trip[] — each with fare, currency, destination as name.
    """
    cookie_header = require_cookies(params, "list_trips")

    types = [t.strip() for t in order_types.split(",")]
    variables = {
        "includePast": True,
        "includeUpcoming": False,
        "limit": min(int(limit), 50),
        "orderTypes": types,
        "profileType": profile_type,
    }
    if next_page_token:
        variables["nextPageToken"] = next_page_token

    data = _gql(cookie_header, "Activities", ACTIVITIES_QUERY, variables)
    activities = data.get("activities", {})
    past = activities.get("past", {})
    raw_trips = past.get("activities") or []

    trips = []
    for t in raw_trips:
        fare_str = t.get("description") or ""
        total_amount, currency = _parse_fare(fare_str)

        trips.append({
            # Standard fields
            "id": t.get("uuid"),
            "name": t.get("title"),  # destination name
            "image": (t.get("imageURL") or {}).get("light"),
            "url": t.get("cardURL"),
            "datePublished": t.get("subtitle"),
            # Trip shape fields
            "trip_type": "ride",
            "status": "completed",
            "fare": fare_str or None,
            "fare_amount": total_amount,
            "currency": currency,
        })

    return trips


def get_trip(trip_id: str, **params) -> dict:
    """Get full trip details.

    Returns: trip with driver→person, origin→place, destination→place, legs→leg[].
    Multi-stop rides have multiple legs (one per waypoint pair).
    """
    cookie_header = require_cookies(params, "get_trip")

    data = _gql(
        cookie_header,
        "GetTrip",
        GET_TRIP_QUERY,
        {"tripUUID": trip_id},
    )

    result = data.get("getTrip", {})
    trip = result.get("trip", {})
    receipt = result.get("receipt") or {}
    waypoints = trip.get("waypoints") or []

    fare_str = trip.get("fare") or ""
    fare_amount, currency = _parse_fare(fare_str)
    status_raw = (trip.get("status") or "").lower()

    driver_name = trip.get("driver") or ""
    driver_parts = driver_name.split(None, 1) if driver_name else []

    distance = f"{receipt.get('distance', '')} {receipt.get('distanceLabel', '')}".strip() or None

    out = {
        # Standard fields
        "id": trip.get("uuid") or trip.get("jobUUID"),
        "name": waypoints[-1] if waypoints else trip_id,
        "image": result.get("mapURL"),
        "datePublished": trip.get("beginTripTime"),
        # Trip shape fields
        "trip_type": "ride",
        "status": status_raw,
        "departure_time": trip.get("beginTripTime"),
        "arrival_time": trip.get("dropoffTime"),
        "duration": receipt.get("duration"),
        "distance": distance,
        "vehicle_type": receipt.get("vehicleType"),
        "fare": fare_str or None,
        "fare_amount": fare_amount,
        "currency": currency,
        "rating": result.get("rating") or None,
        "is_surge": trip.get("isSurgeTrip", False),
        "is_scheduled": trip.get("isScheduledRide", False),
        "stops": max(0, len(waypoints) - 2) if waypoints else 0,
    }

    # Typed references — return data directly, engine infers type from shape relations
    if driver_name:
        out["driver"] = {
            "name": driver_name,
            "first_name": driver_parts[0] if driver_parts else None,
            "last_name": driver_parts[1] if len(driver_parts) > 1 else None,
        }

    if waypoints:
        out["origin"] = {"id": waypoints[0], "name": waypoints[0], "full_address": waypoints[0], "feature_type": "address"}
        out["destination"] = {"id": waypoints[-1], "name": waypoints[-1], "full_address": waypoints[-1], "feature_type": "address"}

    # Build legs from waypoint pairs (multi-stop support)
    if len(waypoints) >= 2:
        trip_id = trip.get("uuid") or trip.get("jobUUID") or trip_id
        out["legs"] = [
            {
                "id": f"{trip_id}_leg_{i + 1}",
                "name": f"Leg {i + 1}: {waypoints[i + 1]}",
                "sequence": i + 1,
                "origin": {"id": waypoints[i], "name": waypoints[i], "full_address": waypoints[i], "feature_type": "address"},
                "destination": {"id": waypoints[i + 1], "name": waypoints[i + 1], "full_address": waypoints[i + 1], "feature_type": "address"},
            }
            for i in range(len(waypoints) - 1)
        ]

    if (result.get("organization") or {}).get("name"):
        out["carrier"] = {"name": result["organization"]["name"]}

    return out


# ---------------------------------------------------------------------------
# Eats helpers
# ---------------------------------------------------------------------------
# Eats API docs: agentos-community/skills/uber/requirements.md
# E2E spec: docs/specs/uber-eats-e2e.md
# Connection docs: agentos-community/docs/skills/connections.md
# ---------------------------------------------------------------------------

def _eats_post(cookie_header: str, endpoint: str, body: dict | None = None) -> dict:
    """POST to Uber Eats RPC API. Endpoint is just the operation name (e.g. 'getPastOrdersV1').

    Uses http.headers() for proper browser UA/sec-ch-* headers — some Eats endpoints
    (notably getReceiptByWorkflowUuidV1) return 500 without them.
    See docs/skills/sdk.md for http.headers() knobs.
    """
    resp = http.post(
        f"{EATS_API_BASE}/{endpoint}",
        cookies=cookie_header,
        json=body or {},
        **http.headers(waf="cf", accept="json", extra=EATS_EXTRA_HEADERS),
    )

    status = resp.get("status") or 0
    body_str = resp.get("body") or ""
    url_final = resp.get("url") or ""

    if status != 200:
        if "auth.uber.com" in body_str or "auth.uber.com" in url_final:
            raise RuntimeError("SESSION_EXPIRED: Uber Eats redirected to login — cookies expired.")
        raise RuntimeError(f"Uber Eats HTTP {status} endpoint={endpoint} body={body_str[:300]}")

    data = resp.get("json")
    if not data or not isinstance(data, dict):
        raise RuntimeError(f"Uber Eats non-JSON: status={status} body={body_str[:300]}")

    if data.get("status") == "failure":
        err = data.get("data", {})
        meta = err.get("meta", {}).get("info", {})
        msg = err.get("message", "") or meta.get("body", {}).get("message", "")
        code = err.get("code", "") or meta.get("statusCode", "")
        # Include raw response for debugging — the Eats API sometimes returns empty error messages
        raise RuntimeError(f"Uber Eats API error: {msg} code={code} endpoint={endpoint} raw={body_str[:500]}")

    return data.get("data", {})


# ---------------------------------------------------------------------------
# Eats operations
# ---------------------------------------------------------------------------
# These use the "eats" connection (.ubereats.com cookies).
# See skill.yaml for connection definition.
# See requirements.md for full API shape documentation.
# ---------------------------------------------------------------------------

def check_eats_session(**params) -> dict:
    """Validate Uber Eats session cookies."""
    cookie_header = get_cookies(params)
    if not cookie_header:
        return {"authenticated": False, "error": "no cookies"}

    try:
        data = _eats_post(cookie_header, "getUserV1", {"shouldGetSubsMetadata": True})
    except RuntimeError as e:
        return {"authenticated": False, "error": str(e)}

    # getUserV1 returns user profile data — if we get here, session is valid
    user = data.get("user", data)
    name = user.get("name") or user.get("firstName", "")
    email = user.get("email", "")

    return {
        "authenticated": True,
        "domain": "ubereats.com",
        "identifier": email or name or "unknown",
        "display": name or email,
    }


def list_deliveries(cursor: str = "", **params) -> list:
    """List Uber Eats order history as order-shaped entities.

    Returns: order[] — each with store relation (organization) and shipping_address (place).
    Backed by getPastOrdersV1. See requirements.md for full response shape.
    """
    cookie_header = require_cookies(params, "list_deliveries")

    data = _eats_post(cookie_header, "getPastOrdersV1", {"lastWorkflowUUID": cursor})

    order_uuids = data.get("orderUuids") or []
    orders_map = data.get("ordersMap") or {}

    orders = []
    for uuid in order_uuids:
        order = orders_map.get(uuid, {})
        base = order.get("baseEaterOrder") or {}
        store_info = order.get("storeInfo") or {}
        fare = order.get("fareInfo") or {}
        location = store_info.get("location") or {}
        raw_addr = location.get("address") or {}
        if isinstance(raw_addr, str):
            raw_addr = {"eaterFormattedAddress": raw_addr}

        total_cents = fare.get("totalPrice", 0)
        # getPastOrdersV1 doesn't include a currencyCode field.
        # The totalPrice is in local-currency cents. We can't reliably
        # determine the currency from this endpoint alone — leave it to
        # get_delivery (which parses the receipt HTML total with symbol).
        currency = fare.get("currencyCode")  # future-proof if Uber adds it

        # Determine status
        if base.get("isCancelled"):
            status = "cancelled"
        elif base.get("isCompleted"):
            status = "completed"
        else:
            status = "in_progress"

        orders.append({
            # Standard fields
            "id": uuid,
            "name": store_info.get("title", "Unknown store"),
            "image": store_info.get("heroImageUrl"),
            "datePublished": base.get("completedAt") or base.get("lastStateChangeAt"),
            # Order shape fields
            "total": f"{total_cents / 100:.2f}" if total_cents else None,
            "total_amount": total_cents / 100 if total_cents else None,
            "currency": currency,
            "status": status,
            "fare_breakdown": [
                {"label": item.get("label"), "amount": item.get("rawValue"), "key": item.get("key")}
                for item in (fare.get("checkoutInfo") or [])
            ],
            # Typed references — create linked entities in the graph
            # Store is a place (POI), not an organization. See place.yaml.
            "store": {
                "id": store_info.get("uuid"),
                "name": store_info.get("title"),
                "image": store_info.get("heroImageUrl"),
                "feature_type": "poi",
                "full_address": raw_addr.get("eaterFormattedAddress"),
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),
            },
            "shipping_address": {
                "full_address": raw_addr.get("eaterFormattedAddress"),
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),
            } if raw_addr.get("eaterFormattedAddress") else None,
        })

    return orders


def get_delivery(order_uuid: str, **params) -> dict:
    """Get full delivery details including items, quantities, and fare breakdown.

    Uses getReceiptByWorkflowUuidV1 for item data (HTML parsing with lxml).
    Note: getOrderEntityByUuidV1 only works for ACTIVE orders — returns 404 for
    completed ones. See requirements.md for selector documentation.
    """
    cookie_header = require_cookies(params, "get_delivery")

    # timestamp: null is how the browser sends it, but the SDK may serialize differently.
    # If this endpoint returns 500, check that the JSON body matches what the browser sends.
    # See requirements.md for the captured request shape.
    data = _eats_post(cookie_header, "getReceiptByWorkflowUuidV1", {
        "contentType": "WEB_HTML",
        "workflowUuid": order_uuid,
    })

    receipt_html = data.get("receiptData", "")
    receipts = data.get("receiptsForJob") or []
    timestamp = data.get("timestamp")

    # Parse items from receipt HTML using lxml + cssselect
    # Selectors documented in requirements.md under "Item extraction from receipt HTML"
    items = []
    fare = {}

    if receipt_html:
        from lxml import html as lhtml
        doc = lhtml.fromstring(receipt_html)

        # Items: data-testid="shoppingCart_item_title_{uuid}"
        for el in doc.cssselect('[data-testid^="shoppingCart_item_title_"]'):
            uid = el.get("data-testid").replace("shoppingCart_item_title_", "")
            qty_els = doc.cssselect(f'[data-testid="shoppingCart_item_quantity_{uid}"]')
            qty = int(qty_els[0].text_content().strip()) if qty_els else 1
            items.append({
                "name": el.text_content().strip(),
                "quantity": qty,
                "item_uuid": uid,
            })

        # Fare breakdown
        total_el = doc.cssselect('[data-testid="total_fare_amount"]')
        fare["total"] = total_el[0].text_content().strip() if total_el else None

        for key in ("item_subtotal", "delivery_fee", "service_fee", "tip", "delivery_discount", "tax"):
            el = doc.cssselect(f'[data-testid="fare_line_item_amount_{key}"]')
            if el:
                fare[key] = el[0].text_content().strip()

    # Parse total — the receipt HTML total has the currency symbol (e.g. "$214.50")
    total_str = fare.get("total", "")
    total_amount, currency = _parse_fare(total_str)

    return {
        # Standard fields
        "id": order_uuid,
        "name": f"Delivery ({len(items)} items)",
        "datePublished": timestamp,
        # Order shape fields
        "total": fare.get("total"),
        "total_amount": total_amount,
        "currency": currency,
        "status": "completed",
        "fare_breakdown": fare,
        # Typed reference: contains → product[] (engine infers type from shape)
        "contains": [
            {
                "id": item["item_uuid"],
                "name": item["name"],
                "quantity": item["quantity"],
            }
            for item in items
        ],
    }


def get_store(store_uuid: str, **params) -> dict:
    """Get store details and full product catalog.

    Backed by getStoreV1. Returns store metadata (open/orderable, ETA, rating)
    and every available product with title, uuid, price, image.
    See requirements.md for full response shape documentation.
    """
    cookie_header = require_cookies(params, "get_store")

    data = _eats_post(cookie_header, "getStoreV1", {"storeUuid": store_uuid})

    if not data.get("title"):
        raise RuntimeError(f"getStoreV1 returned no store data for {store_uuid} — session may be stale")

    # Extract products from catalogSectionsMap
    # Items are nested: sections → HORIZONTAL_GRID items → payload → standardItemsPayload → catalogItems
    # See requirements.md "getStoreV1" section for the full structure.
    # getStoreV1 may include currencyCode at top level (91 keys — not all documented yet)
    store_currency = data.get("currencyCode") or data.get("currency")
    sections_map = data.get("catalogSectionsMap") or {}
    products = []
    seen_uuids = set()

    for sec_items in sections_map.values():
        if not isinstance(sec_items, list):
            continue
        for item in sec_items:
            if item.get("type") != "HORIZONTAL_GRID":
                continue
            payload = item.get("payload") or {}
            std = payload.get("standardItemsPayload") or {}
            section_title = (std.get("title") or {}).get("title", "")
            for ci in (std.get("catalogItems") or []):
                uid = ci.get("uuid", "")
                if uid in seen_uuids:
                    continue  # items appear in multiple sections — deduplicate
                seen_uuids.add(uid)
                price_cents = ci.get("price", 0)
                # RE principle: preserve raw catalog item for write operations.
                # add_to_cart needs the EXACT fields the API returned — sectionUUID,
                # sellingOption, imageUrl, etc. Don't reconstruct, replay.
                # See docs/reverse-engineering/overview.md "Write operations"
                # Product shape: standard fields + product-specific fields
                products.append({
                    # Standard fields
                    "id": uid,
                    "name": ci.get("title", ""),
                    "image": ci.get("imageUrl"),
                    "text": ci.get("itemDescription"),
                    # Product shape fields
                    "price_amount": price_cents / 100 if price_cents else None,
                    "currency": store_currency,
                    "availability": "in_stock" if ci.get("isAvailable", True) else "out_of_stock",
                    "categories": [section_title] if section_title else [],
                    # Raw catalog item — passed through to add_to_cart verbatim.
                    # RE principle: preserve raw data for write operations.
                    "_raw": ci,
                    "_parent_section_uuid": item.get("catalogSectionUUID", ""),
                })

    location = data.get("location") or {}
    raw_addr = location.get("address") or {}
    address = raw_addr if isinstance(raw_addr, dict) else {"eaterFormattedAddress": str(raw_addr)}

    # isOpen can be True even when the store isn't accepting orders right now.
    # closedMessage tells you when it actually opens (e.g. "Opens Saturday 9:30 AM").
    # Check BOTH is_open AND closed_message to determine real availability.
    rating_data = data.get("rating") or {}

    # A store is a place (POI), not an organization. The organization (brand)
    # is the company (e.g. "Sprouts Farmers Market Inc."). The store is a
    # location of that brand — with address, hours, rating, delivery capability.
    # See place.yaml — modeled after Google Places API.
    return {
        # Standard fields
        "id": data.get("uuid", ""),
        "name": data.get("title", ""),
        "image": (data.get("heroImageUrls") or [None])[0],
        "url": f"https://www.ubereats.com/store/{data.get('slug', '')}",
        # Place shape fields
        "full_address": address.get("eaterFormattedAddress"),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "feature_type": "poi",
        "categories": [c.get("name") for c in (data.get("categories") or []) if c.get("name")],
        "phone": data.get("phoneNumber"),
        "hours": data.get("hours"),
        "business_status": "open" if data.get("isOpen") and not data.get("closedMessage") else "closed",
        "rating": rating_data.get("ratingValue"),
        "review_count": rating_data.get("reviewCount"),
        # delivery/eta/is_orderable are CONTEXTUAL — they depend on the user's
        # delivery address, not intrinsic to the place. Returned here for UX
        # but not part of the place shape.
        "is_orderable": data.get("isOrderable", False),
        "closed_message": data.get("closedMessage"),
        "eta": (data.get("etaRange") or {}).get("text"),
        "brand": {
            "name": data.get("title", ""),
        },
        # Products as product-shaped entities
        "products": products,
        "product_count": len(products),
    }


def search_store(store_uuid: str, query: str, **params) -> dict:
    """Search for products within a store by name.

    Fetches the full catalog via getStoreV1 and filters client-side.
    Good enough for Costco (~165 items). For larger catalogs, may need
    a server-side search endpoint (not yet discovered).
    """
    store = get_store(store_uuid=store_uuid, **params)
    query_lower = query.lower()
    matches = [p for p in store["products"] if query_lower in p["name"].lower()]
    return {
        "store_name": store["name"],
        "query": query,
        "matches": matches,
        "match_count": len(matches),
    }


def list_nearby_stores(**params) -> list:
    """List nearby stores/restaurants available for delivery.

    Backed by getFeedV1. Returns place-shaped entities (POIs) with
    rating, ETA, delivery fee, and image. Uses the user's saved delivery
    address from their Uber Eats session.
    """
    cookie_header = require_cookies(params, "list_nearby_stores")

    data = _eats_post(cookie_header, "getFeedV1?localeCode=en-US", {})

    currency = data.get("currencyCode")
    items = data.get("feedItems") or []

    stores = []
    seen = set()
    for item in items:
        # Extract stores from both REGULAR_STORE and carousel types
        if item.get("type") == "REGULAR_STORE":
            store_data = item.get("store", item)
            _extract_feed_store(store_data, stores, seen, currency)
        elif item.get("type") in ("REGULAR_CAROUSEL", "FEATURED_STORES"):
            for store_data in (item.get("carousel", {}).get("stores") or []):
                _extract_feed_store(store_data, stores, seen, currency)

    return stores


def _extract_feed_store(store_data: dict, out: list, seen: set, currency: str | None):
    """Extract a place-shaped entity from a getFeedV1 store item."""
    uuid = store_data.get("storeUuid", "")
    if not uuid or uuid in seen:
        return
    seen.add(uuid)

    title_obj = store_data.get("title") or {}
    name = title_obj.get("text", "") if isinstance(title_obj, dict) else str(title_obj)
    if not name:
        return

    rating_obj = store_data.get("rating") or {}
    marker = store_data.get("mapMarker") or {}
    images = (store_data.get("image") or {}).get("items") or []
    action = store_data.get("actionUrl", "")

    # Parse meta badges for ETA, delivery fee
    eta = None
    delivery_fee = None
    for badge in (store_data.get("meta") or []):
        badge_type = badge.get("badgeType", "")
        text = badge.get("text", "")
        if badge_type == "ETD":
            eta = text
        elif badge_type in ("FARE", "MembershipBenefit"):
            delivery_fee = text

    # Rating text is "4.7" — parse to float
    rating_val = None
    try:
        rating_val = float(rating_obj.get("text", ""))
    except (ValueError, TypeError):
        pass

    out.append({
        # Standard fields
        "id": uuid,
        "name": name,
        "image": images[0]["url"] if images else None,
        "url": f"https://www.ubereats.com{action}" if action else None,
        # Place shape fields
        "feature_type": "poi",
        "latitude": marker.get("latitude"),
        "longitude": marker.get("longitude"),
        "rating": rating_val,
        "review_count": rating_obj.get("accessibilityText"),
        # Contextual delivery info (depends on user's address, not intrinsic to place)
        "eta": eta,
        "delivery_fee": delivery_fee,
        "currency": currency,
    })


# ---------------------------------------------------------------------------
# Eats cart operations (WRITE — these modify state)
# ---------------------------------------------------------------------------
# API shapes captured from browser XHR hooks — see requirements.md
# "addItemsToDraftOrderV2" and "createDraftOrderV2" sections.
# ---------------------------------------------------------------------------

def _build_cart_item(product: dict, store_uuid: str) -> dict:
    """Build cart item from a product returned by get_store.

    RE principle: REPLAY, don't reconstruct. The product's _raw field has the
    exact catalog item data from getStoreV1. We pass it through with minimal
    additions (shoppingCartItemUuid, storeUuid). See overview.md "Write operations".
    """
    raw = product.get("_raw")
    if not raw:
        raise RuntimeError(
            f"Cart item '{product.get('name', '?')}' has no _raw catalog data. "
            "Products must come from get_store() which preserves raw getStoreV1 data. "
            "RE principle: replay, don't reconstruct — never build write payloads from partial data."
        )

    quantity = product.get("quantity", 1)

    # Validate required fields — fail loudly, no silent fallbacks.
    # Every field here comes from the raw catalog item. If it's missing,
    # something is wrong with the catalog data, not with our code.
    for required in ("uuid", "sectionUuid", "title", "price", "imageUrl"):
        if not raw.get(required):
            raise RuntimeError(
                f"Catalog item '{raw.get('title', '?')}' missing required field '{required}'. "
                f"Available keys: {list(raw.keys())}. "
                "Check getStoreV1 response shape — field names are case-sensitive."
            )

    purchase = ((raw.get("purchaseInfo") or {}).get("purchaseOptions") or [{}])[0]
    pricing = (raw.get("purchaseInfo") or {}).get("pricingInfo") or {}

    item = {
        "uuid": raw["uuid"],
        "shoppingCartItemUuid": str(uuid_mod.uuid4()),
        "storeUuid": store_uuid,
        "sectionUuid": raw["sectionUuid"],
        "subsectionUuid": raw.get("subsectionUuid", ""),
        "title": raw["title"],
        "price": raw["price"],
        "quantity": quantity,
        "imageURL": raw["imageUrl"],
        "specialInstructions": "",
        "customizations": {},
        "fulfillmentIssueAction": {
            "type": "STORE_REPLACE_ITEM",
            "itemSubstitutes": None,
            "selectionSource": "UBER_SUGGESTED",
            "storeReplaceItem": {"preferredReplacementType": "SIMILAR_ITEM"},
        },
    }

    # sellingOption and pricedByUnit from purchaseInfo (where the browser gets them)
    if purchase.get("soldByUnit"):
        item["sellingOption"] = {"soldByUnit": purchase["soldByUnit"]}
        if purchase.get("quantityConstraintsV2"):
            item["sellingOption"]["quantityConstraintsV2"] = purchase["quantityConstraintsV2"]
    if pricing.get("pricedByUnit"):
        item["pricedByUnit"] = pricing["pricedByUnit"]
    if purchase.get("soldByUnit"):
        item["soldByUnit"] = purchase["soldByUnit"]

    # itemQuantity
    item["itemQuantity"] = {
        "inSellableUnit": {
            "value": {"coefficient": quantity, "exponent": 0},
            "measurementUnit": purchase.get("soldByUnit") or {"measurementType": "MEASUREMENT_TYPE_COUNT",
                                "length": None, "weight": None, "volume": None},
            "measurementUnitAbbreviationText": None,
        },
        "inPriceableUnit": None,
    }

    return item


def add_to_cart(store_uuid: str, items: list, currency_code: str = "USD", **params) -> dict:
    """Add items to an Uber Eats cart for a store.

    items: list of product dicts from get_store (must include _raw field).
    Each item can have an optional "quantity" field (default 1).
    currency_code: ISO 4217 code (from get_store's currency field, defaults to USD).

    Discards any existing draft for this store and creates a fresh one with
    ALL items inline via createDraftOrderV2 — the same pattern the browser uses
    for the Reorder button. This avoids addItemsToDraftOrderV2 which needs
    additional session state we don't have.

    RE principle: replay, don't reconstruct. See overview.md "Write operations".
    This is a WRITE operation — it modifies cart state.
    """
    cookie_header = require_cookies(params, "add_to_cart")

    if not items:
        return {"error": "no items to add"}

    # Discard any existing draft for this store so we start clean
    drafts_data = _eats_post(cookie_header, "getDraftOrdersByEaterUuidV1", {"removeAdapters": True})
    for draft in (drafts_data.get("draftOrders") or []):
        if draft.get("storeUuid") == store_uuid:
            _eats_post(cookie_header, "discardDraftOrderV2", {"draftOrderUUID": draft["uuid"]})

    # Build cart items from raw catalog data (replay, don't reconstruct)
    cart_items = [_build_cart_item(item, store_uuid) for item in items]

    # Create draft order with ALL items inline — this is what the browser does
    # for the Reorder button. One call, all items, correct catalog data.
    create_body = {
        "isMulticart": True,
        "shoppingCartItems": cart_items,
        "removeAdapters": True,
        "useCredits": True,
        "extraPaymentProfiles": [],
        "promotionOptions": {
            "autoApplyPromotionUUIDs": [],
            "selectedPromotionInstanceUUIDs": [],
            "skipApplyingPromotion": False,
        },
        "deliveryTime": {"asap": True},
        "deliveryType": "ASAP",
        "currencyCode": currency_code,
        "interactionType": "door_to_door",
        "checkMultipleDraftOrdersCap": True,
        "actionMeta": {"isQuickAdd": True},
        "analyticsRelevantData": {"profileSource": ""},
        "businessDetails": {},
    }
    data = _eats_post(cookie_header, "createDraftOrderV2", create_body)

    # Extract result from the create response
    draft = data.get("draftOrder", data)
    draft_uuid = draft.get("uuid", "")
    cart = draft.get("shoppingCart") or {}
    final_items = cart.get("items") or []

    # Return order-shaped (status: draft) with contains → product[]
    total_cents = sum(i.get("price", 0) * i.get("quantity", 1) for i in final_items)
    draft_currency = data.get("currencyCode") or draft.get("currencyCode")
    return {
        # Standard fields
        "id": draft_uuid,
        "name": f"Cart ({len(final_items)} items)",
        # Order shape fields
        "status": "draft",
        "total_amount": total_cents / 100 if total_cents else None,
        "currency": draft_currency,
        "contains": [
            {
                "id": i.get("uuid"),
                "name": i.get("title"),
                "image": i.get("imageURL"),
                "price_amount": i.get("price", 0) / 100 if i.get("price") else None,
                "currency": draft_currency,
                "quantity": i.get("quantity", 1),
            }
            for i in final_items
        ],
    }


def get_cart(**params) -> list:
    """Get current Uber Eats carts as order-shaped entities (status: draft).

    Returns: order[] — each draft order with store (organization) and contains (product[]).
    """
    cookie_header = require_cookies(params, "get_cart")

    drafts_data = _eats_post(cookie_header, "getDraftOrdersByEaterUuidV1", {"removeAdapters": True})
    orders = []
    for draft in (drafts_data.get("draftOrders") or []):
        cart = draft.get("shoppingCart") or {}
        items = cart.get("items") or []
        store = draft.get("storeInfo") or {}
        if not items:
            continue

        total_cents = sum(i.get("price", 0) * i.get("quantity", 1) for i in items)
        cart_currency = draft.get("currencyCode")

        orders.append({
            # Standard fields
            "id": draft.get("uuid"),
            "name": store.get("title") or draft.get("storeUuid", "Unknown store"),
            "datePublished": draft.get("createdAt"),
            # Order shape fields
            "status": "draft",
            "total_amount": total_cents / 100 if total_cents else None,
            "currency": cart_currency,
            "store": {
                "id": draft.get("storeUuid"),
                "name": store.get("title"),
                "image": store.get("heroImageUrl"),
                "feature_type": "poi",
            } if store.get("title") or draft.get("storeUuid") else None,
            "contains": [
                {
                    "id": i.get("skuUUID") or i.get("uuid"),
                    "name": i.get("title"),
                    "image": i.get("imageURL"),
                    "quantity": i.get("quantity", 1),
                    "currency": cart_currency,
                }
                for i in items
            ],
        })

    return orders


def clear_cart(draft_order_uuid: str, **params) -> dict:
    """Discard a draft order (clear the cart for a store)."""
    cookie_header = require_cookies(params, "clear_cart")
    _eats_post(cookie_header, "discardDraftOrderV2", {"draftOrderUUID": draft_order_uuid})
    return {"status": "cleared", "draft_order_uuid": draft_order_uuid}


def checkout(draft_order_uuid: str, **params) -> dict:
    """Place an Uber Eats order from a draft cart.

    WRITE operation — spends money. Requires explicit user consent via firewall.

    Calls getCheckoutPresentationV1 to get the checkout session and payment info,
    then checkoutOrdersByDraftOrdersV1 to place the order.

    RE principle: replay, don't reconstruct. The checkout request shape was captured
    from a live browser order placement. See requirements.md for the full shape.
    """
    cookie_header = require_cookies(params, "checkout")

    # Step 1: Get checkout presentation — we need the checkout session UUID,
    # payment profile, and total fare from this response.
    presentation = _eats_post(cookie_header, "getCheckoutPresentationV1", {
        "payloadTypes": [
            "paymentBarPayload", "total", "subtotal", "upfrontTipping",
            "promotion", "fareBreakdown", "eta", "restrictedItems",
            "orderConfirmations", "paymentProfilesEligibility",
        ],
        "draftOrderUUIDs": [draft_order_uuid],
    })

    # Extract total and currency
    total_payload = presentation.get("checkoutPayloads", {}).get("total", {})
    total_obj = total_payload.get("total", {})
    total_value = total_obj.get("value", {})
    total_e5 = total_value.get("amountE5", 0)
    currency = total_value.get("currencyCode", "USD")

    # Extract payment profile from draft orders
    drafts = presentation.get("draftOrders") or []
    draft = drafts[0] if drafts else {}
    payment_uuid = draft.get("paymentProfileUUID", "")

    # Extract checkout action result params (session UUID + payment plan)
    # This comes from the presentation response's validation/action flow
    checkout_session = str(uuid_mod.uuid4())

    # Step 2: Place the order
    checkout_body = {
        "draftOrderUUID": draft_order_uuid,
        "storeInstructions": "",
        "extraPaymentData": "",
        "shareCPFWithRestaurant": False,
        "extraParams": {
            "timezone": "America/Chicago",
            "trackingCode": "",
            "paymentIntent": "personal",
            "paymentProfileTokenType": "braintree",
            "paymentProfileUuid": payment_uuid,
            "isNeutralZoneEnabled": True,
            "isScheduledOrder": False,
            "orderTotalFare": total_e5,
            "orderCurrency": currency,
            "checkoutType": "drafting",
            "cookieConsent": True,
            "isAddOnOrder": False,
            "isBillSplitOrder": False,
            "isDraftOrderParticipant": False,
            "isEditScheduledOrder": False,
        },
        "currentEaterConsent": {"defaultOptIn": False, "eaterConsented": False},
        "newEaterConsented": False,
        "isGroupOrder": False,
        "bypassAuthDeclineForTrustedUser": False,
        "checkoutActionResultParams": {
            "value": _json.dumps({
                "checkoutSessionUUID": checkout_session,
                "actionResults": [],
                "estimatedPaymentPlan": {
                    "defaultPaymentProfile": {
                        "paymentProfileUUID": payment_uuid,
                        "currencyAmount": {"amountE5": total_e5, "currencyCode": currency},
                    },
                    "useCredits": True,
                },
            })
        },
        "skipOrderRequestedEvent": False,
    }

    data = _eats_post(cookie_header, "checkoutOrdersByDraftOrdersV1", checkout_body)

    total_amount = total_e5 / 100000 if total_e5 else None

    return {
        "id": draft_order_uuid,
        "name": f"Order placed (${total_amount:.2f})" if total_amount else "Order placed",
        "status": "placed",
        "total": total_obj.get("formattedValue"),
        "total_amount": total_amount,
        "currency": currency,
    }


def track_delivery(order_uuid: str = "", **params) -> dict:
    """Track a live Uber Eats delivery — courier location, ETA, progress, item fulfillment.

    Backed by getActiveOrdersV1 + getOrderEntityByUuidV1.
    If order_uuid is omitted, auto-discovers the current active order.
    Returns order with delivery→trip (courier as driver→person, vehicle),
    and item fulfillment states (PENDING, FOUND, REPLACED, NOT_FOUND).
    """
    cookie_header = require_cookies(params, "track_delivery")

    # Discover active order UUID if not provided
    if not order_uuid:
        discover_data = _eats_post(cookie_header, "getActiveOrdersV1", {
            "orderUuid": None,
            "timezone": "America/Chicago",
            "showAppUpsellIllustration": True,
            "isDirectTracking": False,
        })
        discover_orders = discover_data.get("orders") or []
        if not discover_orders:
            return {"status": "not_found", "error": "No active deliveries"}
        # The order UUID can be in several places — try them all
        first = discover_orders[0]
        order_uuid = (
            first.get("orderInfo", {}).get("orderUuid")
            or first.get("orderUUID")
            or first.get("uuid")
            or first.get("activeOrderOverview", {}).get("orderUuid")
            or ""
        )
        if not order_uuid:
            # Debug: return the keys we see so we can find the UUID
            return {"status": "not_found", "error": "No UUID found in active order",
                    "_debug_keys": list(first.keys()),
                    "_debug_orderInfo_keys": list(first.get("orderInfo", {}).keys())}

    active_data = _eats_post(cookie_header, "getActiveOrdersV1", {
        "orderUuid": order_uuid,
        "timezone": "America/Chicago",
        "showAppUpsellIllustration": True,
        "isDirectTracking": False,
    })

    entity_data = _eats_post(cookie_header, "getOrderEntityByUuidV1", {
        "orderUUID": order_uuid,
        "workflowUuid": order_uuid,
    })

    # Parse active order
    orders = active_data.get("orders") or []
    if not orders:
        return {"id": order_uuid, "status": "not_found", "error": "No active order found"}

    order = orders[0]
    status_obj = order.get("activeOrderStatus") or {}
    info = order.get("orderInfo") or {}
    contacts = order.get("contacts") or []
    overview = order.get("activeOrderOverview") or {}

    # Extract delivery address from the delivery feed card (always present)
    delivery_card = next((c.get("delivery") for c in (order.get("feedCards") or []) if c.get("type") == "delivery"), None) or {}

    # Courier from contacts + map entities
    courier_contact = next((c for c in contacts if c.get("type") == "COURIER"), None)
    courier_cards = []
    for card in (order.get("feedCards") or []):
        if card.get("courier"):
            courier_cards = card["courier"]

    courier_loc = None
    courier_path = None
    route_polyline = None
    for card in (order.get("backgroundFeedCards") or []):
        for entity in (card.get("mapEntity") or []):
            if entity.get("type") == "COURIER":
                courier_loc = {"latitude": entity.get("latitude"), "longitude": entity.get("longitude")}
                courier_path = entity.get("pathPoints")
                legs = entity.get("routelineLegs") or []
                if legs:
                    route_polyline = legs[0].get("encodedPolyline")

    # Parse item fulfillment from order entity
    entity = entity_data.get("orderEntity") or {}
    cart = entity.get("cart", {}).get("shoppingCart", {})
    items_raw = cart.get("items") or []

    items = []
    for item in items_raw:
        fc = item.get("fulfillmentContext") or {}
        fs = fc.get("fulfillmentState") or {}
        items.append({
            "id": item.get("skuUUID") or item.get("itemID", {}).get("catalogItemUUID"),
            "name": item.get("title"),
            "image": item.get("imageURL"),
            "quantity": item.get("quantity", 1),
            "fulfillment_state": fs.get("type", "UNKNOWN"),
        })

    # Count fulfillment states
    state_counts = {}
    for i in items:
        s = i["fulfillment_state"]
        state_counts[s] = state_counts.get(s, 0) + 1

    # Build the delivery trip
    phase = (status_obj.get("titleSummary") or {}).get("summary", {}).get("text", "")
    eta = (status_obj.get("subtitleSummary") or {}).get("summary", {}).get("text", "")

    # Latest arrival from status card
    status_cards = [c for c in (order.get("feedCards") or []) if c.get("type") == "status"]
    status_card = status_cards[0].get("status", {}) if status_cards else {}
    latest_arrival = (status_card.get("statusSummary") or {}).get("text", "")

    courier_info = courier_cards[0] if courier_cards else {}

    result = {
        "id": order_uuid,
        "name": overview.get("title") or info.get("storeInfo", {}).get("name"),
        "status": phase.lower().replace("...", "").replace("…", "").strip() or "active",
        "eta": eta,
        "latest_arrival": latest_arrival or None,
        "progress": status_obj.get("currentProgress"),
        "progress_total": status_obj.get("totalProgressSegments"),
        "total": overview.get("subtitle"),
        "item_states": state_counts,
        "contains": items,
    }

    # Delivery trip with courier
    trip_data = {
        "trip_type": "delivery",
        "status": "in_progress",
        "eta": eta,
    }

    # Driver as person — engine knows trip.driver → person from shape
    if courier_contact:
        person_data = {
            "name": courier_contact.get("title"),
        }
        if courier_contact.get("formattedPhoneNumber"):
            person_data["phone"] = courier_contact["formattedPhoneNumber"]
        if courier_info.get("iconUrl"):
            person_data["image"] = courier_info["iconUrl"]
        trip_data["driver"] = person_data

    # Parse vehicle from courier card: description="YUSIEL is in a Toyota RAV4", title="YUSIEL • VVL5357"
    desc = courier_info.get("description") or ""
    title_str = courier_info.get("title") or ""
    plate = title_str.split("•")[-1].strip() if "•" in title_str else None
    vehicle_name = desc.split(" is in a ")[-1] if " is in a " in desc else None
    vehicle_parts = vehicle_name.split(None, 1) if vehicle_name else []

    if vehicle_name:
        trip_data["vehicle_type"] = vehicle_name

    # Courier GPS location as a leg with trace
    if courier_loc:
        leg_data = {
            "id": f"{order_uuid}_leg_1",
            "name": f"Delivery leg",
            "sequence": 1,
        }
        if courier_loc.get("latitude") and courier_loc.get("longitude"):
            leg_data["trace"] = [courier_loc]
        if courier_path:
            leg_data["trace"] = courier_path
        if route_polyline:
            leg_data["polyline"] = route_polyline
        trip_data["legs"] = [leg_data]

    # Store as origin
    store_info = info.get("storeInfo") or {}
    store_loc = store_info.get("location") or {}
    if store_info.get("name"):
        store_addr = (store_loc.get("address") or {}).get("eaterFormattedAddress")
        trip_data["origin"] = {
            "id": store_info.get("uuid") or store_addr or store_info["name"],
            "name": store_info["name"],
            "full_address": store_addr,
            "latitude": store_loc.get("latitude"),
            "longitude": store_loc.get("longitude"),
            "feature_type": "poi",
        }

    # Delivery address as destination
    delivery_addr = info.get("deliveryAddress") or {}
    card_addr = delivery_card.get("address") or {}
    dest_address = delivery_addr.get("address") or card_addr.get("formattedAddress")
    if dest_address:
        eater_entity = next(
            (e for card in (order.get("backgroundFeedCards") or [])
             for e in (card.get("mapEntity") or [])
             if e.get("type") == "EATER"),
            None,
        )
        dest_place = {
            "id": dest_address,
            "name": dest_address,
            "full_address": dest_address,
            "feature_type": "address",
        }
        if eater_entity:
            dest_place["latitude"] = eater_entity.get("latitude")
            dest_place["longitude"] = eater_entity.get("longitude")
        trip_data["destination"] = dest_place

    result["delivery"] = trip_data

    return result
