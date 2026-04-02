"""Uber skill — rides (GraphQL) and Eats (RPC) via browser session cookies."""

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
) -> dict:
    """List past trips with pagination support."""
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
    token = past.get("nextPageToken")

    trips = []
    for t in raw_trips:
        trips.append({
            "trip_id": t.get("uuid"),
            "destination": t.get("title"),
            "fare": t.get("description"),
            "date": t.get("subtitle"),
            "map_url": (t.get("imageURL") or {}).get("light"),
            "detail_url": t.get("cardURL"),
        })

    result = {"trips": trips, "count": len(trips)}
    if token:
        result["next_page_token"] = token
    return result


def get_trip(trip_id: str, **params) -> dict:
    """Get full trip details including receipt."""
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

    return {
        "trip_id": trip.get("uuid") or trip.get("jobUUID"),
        "status": trip.get("status"),
        "driver": trip.get("driver"),
        "pickup": waypoints[0] if len(waypoints) > 0 else None,
        "dropoff": waypoints[1] if len(waypoints) > 1 else None,
        "fare": trip.get("fare"),
        "distance": f"{receipt.get('distance', '')} {receipt.get('distanceLabel', '')}".strip() or None,
        "duration": receipt.get("duration"),
        "vehicle_type": receipt.get("vehicleType"),
        "begin_time": trip.get("beginTripTime"),
        "dropoff_time": trip.get("dropoffTime"),
        "map_url": result.get("mapURL"),
        "rating": result.get("rating"),
        "is_surge": trip.get("isSurgeTrip", False),
        "is_scheduled": trip.get("isScheduledRide", False),
        "is_reserve": trip.get("isUberReserve", False),
        "marketplace": trip.get("marketplace"),
        "organization": (result.get("organization") or {}).get("name"),
    }


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


def list_deliveries(cursor: str = "", **params) -> dict:
    """List Uber Eats order history. Returns orders with store, total, status, timestamps.

    Backed by getPastOrdersV1. See requirements.md for full response shape.
    """
    cookie_header = require_cookies(params, "list_deliveries")

    data = _eats_post(cookie_header, "getPastOrdersV1", {"lastWorkflowUUID": cursor})

    order_uuids = data.get("orderUuids") or []
    orders_map = data.get("ordersMap") or {}
    pagination = data.get("paginationData") or {}

    deliveries = []
    for uuid in order_uuids:
        order = orders_map.get(uuid, {})
        base = order.get("baseEaterOrder") or {}
        store = order.get("storeInfo") or {}
        fare = order.get("fareInfo") or {}
        location = store.get("location") or {}
        address = location.get("address") or {}

        # Prices are in cents
        total_cents = fare.get("totalPrice", 0)

        deliveries.append({
            "id": uuid,
            "name": store.get("title", "Unknown store"),
            "store_uuid": store.get("uuid"),
            "store_image": store.get("heroImageUrl"),
            "store_address": address.get("eaterFormattedAddress"),
            "total": f"${total_cents / 100:.2f}" if total_cents else None,
            "total_cents": total_cents,
            "is_completed": base.get("isCompleted", False),
            "is_cancelled": base.get("isCancelled", False),
            "completed_at": base.get("completedAt"),
            "datePublished": base.get("completedAt") or base.get("lastStateChangeAt"),
            "fare_breakdown": [
                {"label": item.get("label"), "amount": item.get("rawValue"), "key": item.get("key")}
                for item in (fare.get("checkoutInfo") or [])
            ],
        })

    result = {"deliveries": deliveries, "count": len(deliveries)}
    next_cursor = pagination.get("nextCursor")
    if next_cursor:
        result["next_cursor"] = next_cursor
    return result


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

    return {
        "id": order_uuid,
        "items": items,
        "item_count": len(items),
        "fare": fare,
        "timestamp": timestamp,
        "receipts": [
            {"timestamp": r.get("timestamp"), "type": r.get("type")}
            for r in receipts
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

    # Extract products from catalogSectionsMap
    # Items are nested: sections → HORIZONTAL_GRID items → payload → standardItemsPayload → catalogItems
    # See requirements.md "getStoreV1" section for the full structure.
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
                products.append({
                    "name": ci.get("title", ""),
                    "uuid": uid,
                    "price": f"${price_cents / 100:.2f}" if price_cents else None,
                    "price_cents": price_cents,
                    "image": ci.get("imageUrl"),
                    "text": ci.get("itemDescription"),
                    "category": section_title,
                    "is_available": ci.get("isAvailable", True),
                    # Section UUIDs needed by add_to_cart — see requirements.md addItemsToDraftOrderV2
                    "_section_uuid": ci.get("sectionUUID") or item.get("catalogSectionUUID", ""),
                    "_subsection_uuid": item.get("catalogSectionUUID", ""),
                })

    location = data.get("location") or {}
    raw_addr = location.get("address") or {}
    address = raw_addr if isinstance(raw_addr, dict) else {"eaterFormattedAddress": str(raw_addr)}

    # isOpen can be True even when the store isn't accepting orders right now.
    # closedMessage tells you when it actually opens (e.g. "Opens Saturday 9:30 AM").
    # Check BOTH is_open AND closed_message to determine real availability.
    return {
        "name": data.get("title", ""),
        "id": data.get("uuid", ""),
        "is_open": data.get("isOpen", False),
        "is_orderable": data.get("isOrderable", False),
        "closed_message": data.get("closedMessage"),
        "eta": (data.get("etaRange") or {}).get("text"),
        "rating": (data.get("rating") or {}).get("ratingValue"),
        "review_count": (data.get("rating") or {}).get("reviewCount"),
        "address": address.get("eaterFormattedAddress"),
        "hours": data.get("hours"),
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


# ---------------------------------------------------------------------------
# Eats cart operations (WRITE — these modify state)
# ---------------------------------------------------------------------------
# API shapes captured from browser XHR hooks — see requirements.md
# "addItemsToDraftOrderV2" and "createDraftOrderV2" sections.
# ---------------------------------------------------------------------------

def _build_cart_item(product: dict, store_uuid: str) -> dict:
    """Build the item shape that addItemsToDraftOrderV2 / createDraftOrderV2 expects.

    Product dict should have: uuid, name, price_cents, image, category (section uuid).
    Shape documented in requirements.md under addItemsToDraftOrderV2.
    """
    return {
        "uuid": product["uuid"],
        "shoppingCartItemUuid": str(uuid_mod.uuid4()),
        "storeUuid": store_uuid,
        "sectionUuid": product.get("_section_uuid", ""),
        "subsectionUuid": product.get("_subsection_uuid", ""),
        "price": product.get("price_cents", 0),
        "title": product.get("name", ""),
        "quantity": product.get("quantity", 1),
        "customizations": {},
        "imageURL": product.get("image", ""),
        "specialInstructions": "",
        "fulfillmentIssueAction": {
            "type": "STORE_REPLACE_ITEM",
            "itemSubstitutes": None,
            "selectionSource": "UBER_SUGGESTED",
        },
        "pricedByUnit": {"measurementType": "MEASUREMENT_TYPE_COUNT"},
        "soldByUnit": {"measurementType": "MEASUREMENT_TYPE_COUNT"},
    }


def _get_or_create_draft(cookie_header: str, store_uuid: str, first_item: dict) -> dict:
    """Get existing draft order for this store, or create a new one with the first item.

    Returns the draft order data dict (with uuid, shoppingCart, etc).
    See requirements.md for createDraftOrderV2 / getDraftOrdersByEaterUuidV1 shapes.
    """
    # Check for existing draft for this store
    drafts_data = _eats_post(cookie_header, "getDraftOrdersByEaterUuidV1", {"removeAdapters": True})
    for draft in (drafts_data.get("draftOrders") or []):
        if draft.get("storeUuid") == store_uuid:
            return draft

    # No existing draft — create one with the first item inline
    # This is how the browser does it: createDraftOrderV2 includes shoppingCartItems
    create_body = {
        "removeAdapters": True,
        "isMulticart": True,
        "useCredits": True,
        "extraPaymentProfiles": [],
        "promotionOptions": {
            "autoApplyPromotionUUIDs": [],
            "selectedPromotionInstanceUUIDs": [],
            "skipApplyingPromotion": False,
        },
        "deliveryTime": {"asap": True},
        "deliveryType": "ASAP",
        "currencyCode": "USD",
        "interactionType": "door_to_door",
        "checkMultipleDraftOrdersCap": True,
        "actionMeta": {"isQuickAdd": True},
        "analyticsRelevantData": {"profileSource": ""},
        "businessDetails": {},
        "shoppingCartItems": [first_item],
    }
    data = _eats_post(cookie_header, "createDraftOrderV2", create_body)
    return data


def add_to_cart(store_uuid: str, items: list, **params) -> dict:
    """Add items to an Uber Eats cart for a store.

    items: list of dicts with at minimum {uuid, name, price_cents, quantity}.
    Extra fields (image, _section_uuid, _subsection_uuid) improve fidelity.

    Creates a new draft order if none exists for this store.
    This is a WRITE operation — it modifies cart state.
    """
    cookie_header = require_cookies(params, "add_to_cart")

    if not items:
        return {"error": "no items to add"}

    # Build cart items
    cart_items = [_build_cart_item(item, store_uuid) for item in items]

    # Get or create draft order (first item goes into create call if new)
    draft = _get_or_create_draft(cookie_header, store_uuid, cart_items[0])
    draft_uuid = draft.get("uuid", "")
    cart_uuid = (draft.get("shoppingCart") or {}).get("uuid", "")

    added = [cart_items[0]["title"]]  # first item was in create or already existed

    # Add remaining items via addItemsToDraftOrderV2
    for cart_item in cart_items[1:]:
        add_body = {
            "items": [cart_item],
            "cartUUID": cart_uuid,
            "draftOrderUUID": draft_uuid,
            "storeUUID": store_uuid,
            "actionMeta": {"isQuickAdd": True},
            "shouldUpdateDraftOrderMetadata": True,
            "isNewCartAbstraction": True,
            "locationType": "GROCERY_STORE",
        }
        _eats_post(cookie_header, "addItemsToDraftOrderV2", add_body)
        added.append(cart_item["title"])

    # Get final cart state
    final_draft = _eats_post(cookie_header, "getDraftOrderByUuidV1", {"draftOrderUuid": draft_uuid})
    final_items = (final_draft.get("shoppingCart") or {}).get("items") or []

    return {
        "draft_order_uuid": draft_uuid,
        "store_uuid": store_uuid,
        "added": added,
        "added_count": len(added),
        "cart_items": [
            {"name": i.get("title"), "quantity": i.get("quantity"), "price": f"${i.get('price', 0)/100:.2f}"}
            for i in final_items
        ],
        "cart_total_items": len(final_items),
    }


def get_cart(**params) -> dict:
    """Get current Uber Eats cart contents across all stores."""
    cookie_header = require_cookies(params, "get_cart")

    drafts_data = _eats_post(cookie_header, "getDraftOrdersByEaterUuidV1", {"removeAdapters": True})
    carts = []
    for draft in (drafts_data.get("draftOrders") or []):
        cart = draft.get("shoppingCart") or {}
        items = cart.get("items") or []
        store = draft.get("storeInfo") or {}
        if items:
            total_cents = sum(i.get("price", 0) * i.get("quantity", 1) for i in items)
            carts.append({
                "draft_order_uuid": draft.get("uuid"),
                "store_name": store.get("title", "Unknown"),
                "store_uuid": draft.get("storeUuid"),
                "items": [
                    {"name": i.get("title"), "quantity": i.get("quantity"), "price": f"${i.get('price', 0)/100:.2f}"}
                    for i in items
                ],
                "item_count": len(items),
                "estimated_subtotal": f"${total_cents / 100:.2f}",
            })
    return {"carts": carts, "cart_count": len(carts)}


def clear_cart(draft_order_uuid: str, **params) -> dict:
    """Discard a draft order (clear the cart for a store)."""
    cookie_header = require_cookies(params, "clear_cart")
    _eats_post(cookie_header, "discardDraftOrderV2", {"draftOrderUUID": draft_order_uuid})
    return {"status": "cleared", "draft_order_uuid": draft_order_uuid}
