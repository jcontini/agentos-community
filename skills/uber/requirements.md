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
// Pagination: pass the nextCursor from response paginationData

// Response (captured 2026-04-02)
{
  "status": "success",
  "data": {
    "orderUuids": ["10a31bc0-...", "91bc1502-...", ...],  // 10 per page
    "ordersMap": {
      "<uuid>": {
        "baseEaterOrder": {
          "uuid": "...",
          "storeUuid": "...",
          "isCancelled": false,
          "isCompleted": true,
          "completedAt": "2026-03-10T22:50:46.000Z",
          "lastStateChangeAt": "...",
          "orderStateChanges": [
            { "stateChangeTime": "...", "type": "CREATED" },
            { "stateChangeTime": "...", "type": "OFFERED" },
            { "stateChangeTime": "...", "type": "ASSIGNED" },
            { "stateChangeTime": "...", "type": "COMPLETED" }
          ],
          "deliveryStateChanges": [
            { "stateChangeTime": "...", "type": "DISPATCHED" }, // many entries
            { "stateChangeTime": "...", "type": "EN_ROUTE_TO_EATER" },
            { "stateChangeTime": "...", "type": "COMPLETED" }
          ]
        },
        "storeInfo": {
          "uuid": "...",
          "heroImageUrl": "https://tb-static.uber.com/...",
          "title": "Costco Wholesale",  // store name!
          "isOpen": false,
          "closedMessage": "Opens at 9:00 AM",
          "location": {
            "address": {
              "address1": "10225 Research Blvd.Suite 1000",
              "city": "Austin", "region": "TX", "postalCode": "78759",
              "country": "US",
              "eaterFormattedAddress": "10225 Research Blvd.Suite 1000, Austin, TX 78759"
            },
            "latitude": 30.3947844,
            "longitude": -97.7447786
          }
        },
        "courierInfo": { "name": "" },  // name empty for completed orders
        "fareInfo": {
          "totalPrice": 21450,  // cents! $214.50
          "checkoutInfo": [
            { "label": "Subtotal", "type": "credit", "rawValue": 179.32, "key": "eats_fare.subtotal" },
            { "label": "Adjustments", "type": "credit", "rawValue": 15.21, "key": "eats.mp.ott.adjustment_up" },
            { "label": "Delivery Fee", "type": "credit", "rawValue": 5.49, "key": "eats.mp.charges.booking_fee" },
            { "label": "Membership Benefit", "type": "debit", "rawValue": -3, "key": "eats.mp.discounts.subscription_basket_dependent_discount" },
            { "label": "Uber One Credits", "type": "debit", "rawValue": -1.2, "key": "eats.mp.discounts.membership.cash_benefit" }
          ]
        },
        "ratingInfo": { "isRatable": true, "userRatings": [] },
        "interactionType": "door_to_door"
      }
    },
    "paginationData": {
      "nextCursor": "{\"entity_type\":\"CONSUMER\",\"cursor\":\"...\"}"
    },
    "meta": { ... }
  }
}
```

Sample data (10 orders from 2026-04-02):
- Sprouts Farmers Market — $194.48
- **Costco Wholesale — $214.50**
- Randalls — $216.21, $144.56
- Desano Pizza Napoletana — $72.01
- Costco Wholesale — $94.57
- 1618 Asian Fusion — $48.23
- Sprouts Farmers Market — $166.40

#### `getReceiptByWorkflowUuidV1` — receipt with item details (discovered 2026-04-02)

This is the KEY endpoint for item-level order data. Not listed in the initial capture because it only fires when viewing a specific order's receipt.

```json
// Request
{
  "contentType": "WEB_HTML",
  "workflowUuid": "91bc1502-a3a4-4a47-8339-12e4d5ae1211",
  "timestamp": null
}

// Response
{
  "status": "success",
  "data": {
    "receiptData": "<!doctype html>...",  // HTML receipt — item names in data-testid attributes
    "isPDFSupported": true,
    "receiptsForJob": [{ "timestamp": "...", "type": "...", "eventUUID": "..." }],
    "timestamp": "2026-03-10T23:20:05.041Z",
    "actions": [{ "type": "...", "helpNodeUUID": "..." }]
  }
}
```

**Item extraction from receipt HTML:**

Items are in divs with `data-testid="shoppingCart_item_title_{uuid}"`. Prices in `data-testid="shoppingCart_item_amount_{uuid}"` (often empty for completed orders).

Parse with CSS selectors:
```python
from lxml import html as lhtml
doc = lhtml.fromstring(receipt_html)
items = []
for el in doc.cssselect('[data-testid^="shoppingCart_item_title_"]'):
    items.append({"name": el.text_content().strip()})
```

**Sample items from Costco order (18 items):**
- Universal Bakery Organic Aussie Bites (30 oz)
- Organic Bananas (48 oz)
- Kirkland Signature Plain Bagels (12 ct)
- Kirkland Signature Smoked Salmon, 12 oz, 2-count
- Taylor Farms Tender Spinach Leaves (16 oz)
- Wilde Protein Crispy Chips, Buffalo Style (8.5 oz)
- Sunset Organic Mixed Bell Peppers
- Sweet Onions, 5 lbs
- Highline Organic Crimini Mushrooms (24 oz)
- Baby Bok Choy, 2 lbs
- Lee Kum Kee Premium Sauce, Oyster (32 oz)
- Mandarins, 3 lbs
- Organic Blueberries, 18 oz
- The Little Potato Company Little Duos Fresh Creamer Potatoes (5 lbs)
- Organic Gala Apples, 3 lbs
- Kirkland Signature Cashews (38 oz)
- MALK Organic Almond Milk, Unsweetened (2 x 48 fl oz)
- Kirkland Signature Rotisserie Chicken

#### `getOrderEntitiesV1` — order entities
```json
// Request
{}

// Response — returns null/empty when called without context.
// May need order UUID param. Currently not the right endpoint for item data.
// Use getReceiptByWorkflowUuidV1 instead.
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
