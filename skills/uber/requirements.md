# Uber — Reverse Engineering Notes

## Rides API (implemented)

### Endpoint
```
POST https://riders.uber.com/graphql
```

### Auth
- Cookie domain: `.uber.com`
- Headers: `x-csrf-token: x`, `x-uber-rv-session-type: desktop_session`
- CSRF token is literally the string `"x"` — not a real rotating token

### GraphQL operations
- `CurrentUserRidersWeb` — user profile with Uber One, payment methods, profiles
- `Activities` — trip history. Supports `orderTypes: ["RIDES", "TRAVEL"]`. Does NOT support `"EATS"`.
- `GetTrip` — full trip detail with driver, fare, receipt, map

### Cookie domain issue (solved)
Uber sets cookies on `.uber.com`, `.riders.uber.com`, `.auth.uber.com`, `.www.uber.com`. Before RFC 6265 filtering, the wrong `csid` cookie from `.auth.uber.com` was sent to `riders.uber.com`, causing login redirects. Fixed in engine — domain matching now filters by `connection.base_url` host.

---

## Uber Eats API (discovery in progress)

### Discovery session (2026-04-02)

Used `bin/browse-capture.py` (CDP network capture) on `ubereats.com/orders`. Brave with CDP on port 9222.

### Endpoint
```
POST https://www.ubereats.com/_p/api/{operationName}
```

This is NOT GraphQL. It's an RPC-style API — each operation has its own URL path. Request and response bodies are JSON.

### Auth

Cookie domain: `.ubereats.com` (different from `.uber.com` for rides — may need a separate connection in skill.yaml)

Required headers:
```
x-csrf-token: x
x-uber-session-id: <from uev2.id.session cookie>
x-uber-target-location-latitude: 30.271044
x-uber-target-location-longitude: -97.695755
x-uber-client-gitref: d55216830edc27ad681f4c3df954d552afa4dea1
x-uber-ciid: <UUID — client instance ID>
x-uber-request-id: <UUID — unique per request>
Content-Type: application/json
```

Notes:
- `x-uber-session-id` comes from the `uev2.id.session` cookie value
- `x-uber-client-gitref` is a version hash — may need periodic updating
- `x-uber-ciid` appears to be a client-generated UUID (stable per session?)
- `x-uber-request-id` is a fresh UUID per request

### Discovered endpoints

#### `getPastOrdersV1` — order history
```json
// Request
{ "lastWorkflowUUID": "" }
// Pagination: pass the lastWorkflowUUID from previous response

// Response: TODO — need to capture response body via CDP Network.getResponseBody
```

#### `getOrderEntitiesV1` — order details
```json
// Request
{}

// Response: TODO
```

#### `getActiveOrdersV1` — live orders
```json
// Request
{
  "orderUuid": null,
  "timezone": "America/Chicago",
  "showAppUpsellIllustration": true,
  "isDirectTracking": false
}

// Response: TODO
```

#### `getCartsViewForEaterUuidV1` — cart state
```json
// Request
{}

// Response: TODO
```

#### `getSearchHomeV2` — store browsing
```json
// Request
{ "dropPastOrders": true }

// Response: TODO — should contain store listings near the user's location
```

#### `getDraftOrdersByEaterUuidV1` — draft orders
```json
// Request
{ "removeAdapters": true }
// or
{ "currencyCode": "USD" }

// Response: TODO
```

#### `getUserV1` — user profile
```json
// Request
{ "shouldGetSubsMetadata": true }

// Response: TODO
```

#### `getProfilesForUserV1` — profiles
```json
// Request
{}

// Response: TODO
```

#### `getInstructionForLocationV1` — delivery instructions
```json
// Request
{
  "location": {
    "address": {
      "address1": "1141 1/4 Gunter St",
      "address2": "Austin, TX",
      "aptOrSuite": "",
      "eaterFormattedAddress": "1141 1/4 Gunter St, Austin, TX 78721-1852, US",
      "subtitle": "Austin, TX",
      "title": "1141 1/4 Gunter St",
      "uuid": ""
    },
    "latitude": 30.271044,
    "longitude": -97.695755,
    "reference": "b69d9fec-14b1-f34a-4759-bf6459bf7c9b",
    "referenceType": "uber_places",
    "type": "uber_places"
  }
}
```

This shows the location/address shape Uber uses internally. Note the `uber_places` reference type.

#### `setRobotEventsV1` — bot detection telemetry
```json
// Request
{
  "action": "rendered",
  "payload": {
    "shouldIndex": false,
    "shouldIndexOverride": true,
    "appVariant": "eats",
    "overrideAvoided": false,
    "isBot": false,
    "page": "unknown"
  }
}
```

This is a bot detection signal. The page sends `isBot: false` — we should do the same if we call this endpoint.

### Real-time events

Two event stream endpoints observed:
- `https://www.ubereats.com/ramenphx/events/recv?seq=0`
- `https://www.ubereats.com/ramendca/events/recv?seq=0`

These appear to be SSE (Server-Sent Events) or long-polling channels for real-time updates. `phx` and `dca` might be datacenter identifiers (Phoenix, DCA). The `seq=0` parameter suggests sequence-based event consumption.

Likely used for:
- Live delivery tracking (driver location, ETA updates)
- Order status changes
- Chat messages from driver

### Payment profiles

```
GET https://payments.ubereats.com/_api/payment-profiles?ctx={latitude,longitude}
```

Separate payment service — note the different subdomain (`payments.ubereats.com`).

### Next steps

1. **Capture response bodies** — enhance `browse-capture.py` with `Network.getResponseBody` to see what each endpoint returns
2. **Capture Costco store page** — `browse capture` on a Costco store URL to discover menu/product endpoints
3. **Document response shapes** — product, order, delivery, driver structures
4. **Determine if `.ubereats.com` cookies work** — the rides skill uses `.uber.com`; Eats may need its own connection
