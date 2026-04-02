# Uber

Ride history, trip details, receipts, and account info from Uber. Uses Uber's internal GraphQL API at `riders.uber.com/graphql` via browser session cookies. Uber Eats uses a separate RPC API at `ubereats.com/_p/api/`.

> **Before extending this skill**, read:
> 1. [Reverse Engineering overview](../../docs/reverse-engineering/overview.md) — methodology, tools, progression
> 2. [Transport & Anti-Bot](../../docs/reverse-engineering/1-transport/index.md) — TLS fingerprinting, WAF bypass, cookie domain filtering
> 3. [requirements.md](./requirements.md) — captured API shapes, endpoint inventory, auth headers
> 4. [Uber Eats E2E spec](../../../docs/specs/uber-eats-e2e.md) — the plan for what we're building

## Features

### Rides
- **`list_trips`** — Ride history with pagination. Returns trip ID, destination, fare, date, and map URL. Supports `profile_type` (PERSONAL/BUSINESS) filter and pagination via `next_page_token`. Max 50 per page.
- **`get_trip`** — Full trip details: driver info, pickup/dropoff addresses, fare breakdown, distance, duration, vehicle type, surge pricing, map URL, and rating.

### Account
- **`whoami`** — Full user profile: name, email, phone, rating, picture URL, Uber One membership, payment methods, and profiles (personal/business).
- **`check_session`** — Validate session cookies and return account identity.

## Setup

Requires an active Uber session in Brave (or another browser). The skill extracts session cookies from the browser's cookie database. No API keys needed.

1. Log in to [riders.uber.com](https://riders.uber.com) in Brave
2. Cookies are extracted automatically when you use the skill

## Transport

Cookie auth against `.uber.com`. The rides API uses a single GraphQL endpoint:

```
POST https://riders.uber.com/graphql
```

Headers:
- `x-csrf-token: x` (literal string, not a real CSRF token)
- `x-uber-rv-session-type: desktop_session`

Three GraphQL operations:
- `CurrentUserRidersWeb` — user profile
- `Activities` — trip history with filtering/pagination
- `GetTrip` — full trip details with receipt

### Cookie domain filtering

Uber has cookies on multiple subdomains (`.uber.com`, `.riders.uber.com`, `.auth.uber.com`). The engine's RFC 6265 domain matching ensures only cookies matching `riders.uber.com` are sent. This prevents `csid` collisions from sibling subdomains that caused login redirects before domain filtering was implemented.

See [Transport & Anti-Bot docs](../../docs/reverse-engineering/1-transport/index.md#cookie-domain-filtering--rfc-6265) for details.

## Uber Eats (in progress)

Uber Eats uses a **completely different API** from rides. It's NOT GraphQL — it's an RPC-style API at `www.ubereats.com/_p/api/`.

### Discovery (2026-04-02)

Used `browse capture` (CDP network capture via `bin/browse-capture.py`) to navigate `ubereats.com/orders` in Brave and capture all API calls. Key findings:

**Uber Eats API endpoints** (all `POST https://www.ubereats.com/_p/api/`):

| Endpoint | Purpose | Request body |
|----------|---------|-------------|
| `getPastOrdersV1` | Order history | `{ "lastWorkflowUUID": "" }` (pagination) |
| `getOrderEntitiesV1` | Order details — items, driver, receipt | `{}` |
| `getActiveOrdersV1` | Live orders in progress | `{ "orderUuid": null, "timezone": "America/Chicago" }` |
| `getCartsViewForEaterUuidV1` | Current cart state | `{}` |
| `getSearchHomeV2` | Store browsing / search | `{ "dropPastOrders": true }` |
| `getDraftOrdersByEaterUuidV1` | Draft (unsent) orders | `{ "removeAdapters": true }` |
| `getUserV1` | User profile for Eats | `{ "shouldGetSubsMetadata": true }` |
| `getProfilesForUserV1` | User profiles | `{}` |
| `getInstructionForLocationV1` | Delivery instructions | `{ "location": { "latitude": ..., "longitude": ... } }` |
| `setRobotEventsV1` | Bot detection telemetry | `{ "action": "rendered", "payload": { "isBot": false } }` |

**Auth headers for Eats** (different from rides):

```
x-csrf-token: x
x-uber-session-id: <from uev2.id.session cookie>
x-uber-target-location-latitude: 30.271044
x-uber-target-location-longitude: -97.695755
x-uber-client-gitref: <client version hash>
x-uber-ciid: <client instance ID>
x-uber-request-id: <UUID per request>
Content-Type: application/json
```

**Cookie domain:** `.ubereats.com` (NOT `.uber.com` — different domain from rides)

**Real-time events:** `ramenphx/events/recv` and `ramendca/events/recv` — likely SSE or long-polling for live delivery tracking updates.

**Key difference from rides:** The `order_types: "EATS"` parameter on the rides GraphQL `Activities` query does NOT work — `EATS` is not a valid enum value in `RVWebCommonActivityOrderType`. Uber Eats order history must be fetched from the Eats-specific `getPastOrdersV1` endpoint.

### Planned Eats operations

See [Uber Eats E2E spec](../../../docs/specs/uber-eats-e2e.md) for the full plan.

Phase 1 (read):
- `list_deliveries` — Eats order history via `getPastOrdersV1`
- `get_delivery` — Full delivery details via `getOrderEntitiesV1`
- `list_stores` — Browse stores via `getSearchHomeV2`
- `get_menu` — Store menu/items

Phase 2 (tracking):
- `track_delivery` — Live driver location via real-time events
- `list_messages` — Driver communication

Phase 3 (write — requires [firewall](../../../docs/specs/firewall.md)):
- `add_to_cart`, `checkout`, `approve_substitution`, `rate_delivery`

## Reverse Engineering Notes

### Tools used

- **`agentos browse request uber`** — authenticated HTTP request with full header visibility. Used to verify cookie auth and inspect response headers.
- **`agentos browse cookies uber`** — cookie inventory showing all `.uber.com` cookies with timestamps and provenance.
- **`agentos browse auth uber`** — auth resolution trace showing which provider won (brave-browser) and identity (uber@contini.co).
- **`bin/browse-capture.py`** — CDP network capture. Connected to Brave via CDP, navigated to `ubereats.com/orders`, captured 90 requests including all `/_p/api/` calls with full headers and POST bodies.

### How to extend

**Step 1: Capture network traffic with CDP**

```bash
# Launch Brave with CDP
open -a "Brave Browser" --args --remote-debugging-port=9222 --remote-allow-origins="*"

# Capture network traffic for any Uber Eats page
python3 bin/browse-capture.py https://www.ubereats.com/store/costco/... --port 9222

# Look for /_p/api/ POST requests in the output
# Response bodies are captured automatically via CDP Network.getResponseBody
```

**Step 2: Extract full API surface from JS bundles**

Don't just capture what one page loads — extract ALL endpoint names from the client JS:

```bash
# Find the main bundle URL from browse-capture output
# Then grep for API endpoint patterns
curl -s "https://www.ubereats.com/_static/client-main-*.js" \
  | grep -oE 'get[A-Z][a-zA-Z]+V[0-9]+' | sort -u   # read endpoints
curl -s "https://www.ubereats.com/_static/client-main-*.js" \
  | grep -oE '[a-z]+[A-Z][a-zA-Z]+V[0-9]+' | sort -u | grep -v '^get'  # write endpoints
```

This revealed 32 endpoints (22 read, 10 write) that weren't visible from a single page capture. The pattern `{verb}{Entity}V{version}` is consistent across all Uber Eats endpoints.

**Step 3: Test individual endpoints**

Use `agentos browse request` or direct `curl` to test specific endpoints. The auth headers and cookie domain are documented in [requirements.md](./requirements.md).

See [Reverse Engineering overview](../../docs/reverse-engineering/overview.md) for the full methodology and [Browse Toolkit spec](../../../docs/specs/browse-toolkit.md) for tool documentation.
