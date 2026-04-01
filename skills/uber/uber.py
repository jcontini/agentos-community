"""Uber skill — ride history, trip details, and account info via GraphQL."""

from agentos import http, get_cookies, require_cookies

GRAPHQL_URL = "https://riders.uber.com/graphql"

HEADERS = {
    "Accept": "*/*",
    "x-csrf-token": "x",
    "x-uber-rv-session-type": "desktop_session",
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
    """Execute a GraphQL query against riders.uber.com."""
    resp = http.post(
        GRAPHQL_URL,
        cookies=cookie_header,
        headers=HEADERS,
        json={
            "operationName": operation_name,
            "query": query,
            "variables": variables or {},
        },
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
