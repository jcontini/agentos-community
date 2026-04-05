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

Cookie domain: `.ubereats.com` (separate connection from `.uber.com` rides — `eats` connection in skill.yaml)

**CRITICAL: Always use `http.headers(waf="cf", accept="json", extra={...})` for all requests.**
The engine sets zero headers by default. Without browser-grade UA/sec-ch-* headers, some endpoints
(notably `getReceiptByWorkflowUuidV1`) return 500. We are acting as Brave — send what Brave sends.
See `agentos-community/docs/skills/sdk.md` for `http.headers()` documentation.

Required Eats-specific headers (pass via `extra=`):
```
x-csrf-token: x                        # literal string "x", same as rides
```

Additional headers the browser sends (optional for basic reads, may be needed for writes):
```
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
- `getPastOrdersV1` works with just `x-csrf-token` but `getReceiptByWorkflowUuidV1` needs full browser headers

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

**Item extraction from receipt HTML (confirmed 2026-04-02):**

Three `data-testid` patterns per item, keyed by item UUID:

| Selector pattern | Content | Notes |
|-----------------|---------|-------|
| `shoppingCart_item_title_{uuid}` | Item name | Always populated |
| `shoppingCart_item_quantity_{uuid}` | Quantity (e.g. "2") | Always populated |
| `shoppingCart_item_amount_{uuid}` | Per-item price | **Empty for completed orders** — prices only visible during active delivery |

Fare breakdown selectors (always populated):

| Selector | Content | Example |
|----------|---------|---------|
| `total_fare_amount` | Total | "$214.50" |
| `fare_line_item_amount_item_subtotal` | Subtotal | "$179.32" |
| `fare_line_item_amount_delivery_fee` | Delivery fee | "$1.89" |
| `fare_line_item_amount_service_fee` | Service fee | "$12.55" |
| `fare_line_item_amount_tip` | Tip | "$11.62" |
| `fare_line_item_amount_delivery_discount` | Discount | "-$1.89" |

Parse with lxml + cssselect (per skill standards — no BS4, no regex on HTML):
```python
from lxml import html as lhtml

doc = lhtml.fromstring(receipt_html)

# Extract items with quantities
items = []
for el in doc.cssselect('[data-testid^="shoppingCart_item_title_"]'):
    uid = el.get("data-testid").replace("shoppingCart_item_title_", "")
    qty_el = doc.cssselect(f'[data-testid="shoppingCart_item_quantity_{uid}"]')
    items.append({
        "name": el.text_content().strip(),
        "quantity": int(qty_el[0].text_content().strip()) if qty_el else 1,
        "item_uuid": uid,
    })

# Extract fare breakdown
total_el = doc.cssselect('[data-testid="total_fare_amount"]')
total = total_el[0].text_content().strip() if total_el else None
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

#### `getOrderEntitiesV1` — order entities (active orders only)
```json
// Request — tested with multiple param shapes (2026-04-02)
{"orderUuids": ["91bc1502-..."]}  // returns null for completed orders
{"workflowUuid": "91bc1502-..."}  // same — null for completed orders
{}                                 // returns null without context

// Response (always empty for completed orders):
{
  "status": "success",
  "data": {
    "orderEntities": null,
    "orderEntitiesView": []
  }
}
// Verdict: only useful during active delivery, not for order history.
```

#### `getOrderEntityByUuidV1` — single order entity (ACTIVE ORDERS ONLY)
```json
// Request — tested 2026-04-02 with completed order UUIDs
{"orderUuid": "10a31bc0-..."}     // 404: "active workflow not found"
{"workflowUuid": "91bc1502-..."}  // 404: "active internal order not found from workflow"

// Response for completed orders:
{
  "status": "failure",
  "data": {
    "message": "status code error",
    "code": 404,
    "meta": {
      "info": {
        "statusCode": "404",
        "body": {
          "code": "not_found.error",
          "message": "NotFoundError{Info: ErrorInfo{Message: active workflow not found}}"
        }
      }
    }
  }
}
// Verdict: ONLY works for in-progress orders. For completed order items,
// use getReceiptByWorkflowUuidV1 and parse the HTML.
// Will be useful in Phase 2 (live tracking) but NOT for Phase 1 (history).
```

#### `getFeedV1` — home feed with nearby stores (captured 2026-04-02)

Returns all stores available for delivery near the user's saved address. 126 feedItems, 97 REGULAR_STORE + carousels.

```json
// Request
// POST https://www.ubereats.com/_p/api/getFeedV1?localeCode=en-US
{}  // empty body — uses user's saved location from cookies

// Response (top-level)
{
  "status": "success",
  "data": {
    "currencyCode": "USD",        // THE CURRENCY CODE — use this everywhere
    "cityName": "austin",
    "isInServiceArea": true,
    "feedItems": [
      // REGULAR_STORE (97 items) — individual store listings
      {
        "uuid": "...",
        "type": "REGULAR_STORE",
        "store": {
          "storeUuid": "31639dbf-5335-5fdb-b5c8-108fce505ed3",
          "title": { "text": "Sprouts Farmers Market" },
          "rating": {
            "text": "4.7",        // parse to float
            "accessibilityText": "A top rated restaurant with 4.7 out of 5 stars based on more than 2,000 reviews.",
            "badgeType": "RATINGS"
          },
          "actionUrl": "/store/sprouts-farmers-market-.../MWOdv1M1X9u1yBCPzlBe0w?diningMode=DELIVERY",
          "image": {
            "items": [
              { "url": "https://tb-static.uber.com/...", "width": 2880, "height": 2304 }
            ]
          },
          "mapMarker": {
            "latitude": 30.3047,
            "longitude": -97.7095
          },
          "meta": [
            // Badge array — ETA, delivery fee, membership benefits
            { "text": "$0 Delivery Fee", "badgeType": "MembershipBenefit" },
            { "text": "35 min", "badgeType": "ETD" }
          ],
          "signposts": [...],       // promotional badges
          "endorsements": [...]     // distance surcharges, etc.
        }
      },
      // REGULAR_CAROUSEL (11 items) — horizontal scrollable rows
      {
        "type": "REGULAR_CAROUSEL",
        "carousel": {
          "stores": [...],         // same store shape as REGULAR_STORE
          "header": { "title": "..." }
        }
      }
    ]
  }
}
```

**Key facts about `getFeedV1`:**
- Empty body `{}` works — location comes from cookies/session
- `currencyCode` at top level is the **authoritative currency** for this market
- `meta` badges have `badgeType: "ETD"` for delivery time, `"MembershipBenefit"` for Uber One fee
- `mapMarker` has lat/lng for the store location
- `image.items[0].url` for the store image (multiple resolutions available)
- Stores appear in both REGULAR_STORE and carousel items — deduplicate by storeUuid

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

### Full API surface (extracted from JS bundles, 2026-04-02)

Extracted by grepping `client-main-*.js` for endpoint name patterns.

**Read operations:**

| Endpoint | Purpose | Status |
|----------|---------|--------|
| `getPastOrdersV1` | Order history with store, fare, timestamps | **Captured** — full response shape documented |
| `getReceiptByWorkflowUuidV1` | Receipt HTML with item names, quantities, fare breakdown | **Captured + parsed** — lxml selectors confirmed working. Item prices empty on completed orders. |
| `getOrderEntityByUuidV1` | Order entity for **active orders only** | **Tested** — returns 404 for completed orders. Only useful during live delivery (Phase 2). |
| `getOrderEntitiesV1` | Order entities for **active orders only** | **Tested** — returns null/empty for completed orders. Only useful during live delivery (Phase 2). |
| `getActiveOrdersV1` | Live order status/tracking | **Captured** — returns feed cards, order phase |
| `getStoreV1` | Store details + full product catalog | **Captured** — 165 Costco items with title, uuid, price, image. See section below. |
| `getPaginatedStoresV1` | Store browsing with pagination | Not yet captured |
| `getFeedV1` | Home feed (store listings) | Not yet captured |
| `getFeedItemsUpdateV1` | Feed updates | Not yet captured |
| `getSearchHomeV2` | Search/browse home | **Captured** — top-level keys only |
| `getCheckoutPresentationV1` | Checkout flow/presentation | Not yet captured |
| `getEaterMessagingContentV1` | Driver messages/chat | Not yet captured |
| `getOriginalCartV1` | Cart before substitutions | Not yet captured |
| `getDraftOrderByUuidV1` / `V2` | Draft order details | Not yet captured |
| `getOrderEntitiesV1` | Order entities (active only — see above) | **Tested** — null for completed, useful in Phase 2 |
| `getUserV1` | User profile | **Captured** |
| `getProfilesForUserV1` | User profiles list | **Captured** |
| `getCartsViewForEaterUuidV1` | Current cart state | **Captured** |
| `getMenuItemV1` | Item customization options (toppings, sizes, sides) | **Captured** — full customization group/option shape documented |
| `getInStoreSearchV1` | In-store product search | **Captured** — same item shape as getStoreV1 |
| `getLocationV1` | Location details | Not yet captured |
| `getNavigationLinksV1` | Nav structure | Not yet captured |
| `getEatsPassV1` | Uber One / Eats Pass | Not yet captured |
| `getUberBalancesV1` | Uber credits/balances | Not yet captured |
| `getInvoiceStatusV1` | Invoice/receipt status | **Captured** |

**Write operations (require [firewall](../../../docs/specs/firewall.md)):**

#### `addItemsToDraftOrderV2` — add items to cart (captured 2026-04-02)

The browser uses **XHR** (not fetch) for this endpoint. The request requires a pre-existing draft order UUID.

```json
// Request — captured from browser quick-add click
{
  "items": [
    {
      "uuid": "f2a36234-4936-577a-...",           // catalog item UUID (from getStoreV1)
      "shoppingCartItemUuid": "503161fb-...",      // NEW client-generated UUID (uuid4)
      "storeUuid": "c928e271-...",                 // store UUID
      "sectionUuid": "d3de65fb-...",               // catalog section UUID (from getStoreV1 structure)
      "subsectionUuid": "9d480d3e-...",            // subsection UUID
      "price": 430.92,                             // price in cents (from getStoreV1)
      "title": "Kirkland Signature Purified Water", // item title
      "quantity": 1,
      "customizations": {},
      "imageURL": "https://tb-static.uber.com/...",
      "specialInstructions": "",
      "fulfillmentIssueAction": {
        "type": "STORE_REPLACE_ITEM",              // default: let store substitute
        "itemSubstitutes": null,
        "selectionSource": "UBER_SUGGESTED"
      },
      "pricedByUnit": { "measurementType": "MEASUREMENT_TYPE_COUNT" },
      "soldByUnit": { "measurementType": "MEASUREMENT_TYPE_COUNT" }
    }
  ],
  "cartUUID": "85cf3299-...",                      // from getDraftOrderByUuidV1
  "draftOrderUUID": "9c7a4af4-...",                // draft order UUID
  "storeUUID": "c928e271-...",                     // store UUID (repeated)
  "actionMeta": { "isQuickAdd": true },
  "shouldUpdateDraftOrderMetadata": true,
  "isNewCartAbstraction": true,
  "locationType": "GROCERY_STORE"
}
```

**Key discovery notes:**
- Browser uses XHR, not fetch — that's why our fetch hook missed it initially
- `shoppingCartItemUuid` is a client-generated UUID (uuid4) — new for each add
- `sectionUuid` and `subsectionUuid` come from the catalog structure in getStoreV1
- `fulfillmentIssueAction.type: "STORE_REPLACE_ITEM"` means "let the store substitute if out of stock"
- `cartUUID` is different from `draftOrderUUID` — get it from `getDraftOrderByUuidV1`
- Without the draft order UUID, returns `MISSING_DRAFT_ORDER_UUID` (404)
- With wrong item shape (e.g. missing fields), returns `empty items` (400)

| Endpoint | Purpose |
|----------|---------|
| `addItemsToDraftOrderV2` | Add items to cart — **captured**, full shape documented above |
| `checkoutOrdersByDraftOrdersV1` | **PLACE ORDER** — **CAPTURED 2026-04-02**. See full request shape below. |
| `cancelOrderV1` | Cancel an active order |
| `getRepeatOrderViewV1` | Repeat order view (not yet tested) |
| `addItemsToGroupDraftOrderV2` | Group order cart |
| `addItemsToOrderV1` | Add items to active order |
| `createDraftOrderV2` | Create new order |
| `confirmCartUpdatesV1` | Confirm substitutions |
| `discardDraftOrderV2` / `V1` | Cancel draft order |
| `removeItemsFromDraftOrderV2` | Remove cart items |
| `applyPromoV1` | Apply promo code |
| `createEaterFavoritesV1` | Add to favorites |
| `deleteEaterFavoritesV1` | Remove from favorites |

#### `checkoutOrdersByDraftOrdersV1` — place order (captured 2026-04-02)

The checkout endpoint. Takes a draft order UUID and places the order.

```json
// Request — captured from live Sprouts order ($81.44, 13 items)
{
  "draftOrderUUID": "2404af12-...",           // from createDraftOrderV2 / getDraftOrdersByEaterUuidV1
  "storeInstructions": "",
  "extraPaymentData": "",
  "shareCPFWithRestaurant": false,
  "extraParams": {
    "timezone": "America/Chicago",
    "trackingCode": "{\"metaInfo\":{\"analyticsLabel\":\"past_orders_reorder\"}}",
    "storeUuid": "31639dbf-...",              // store UUID
    "cityName": "austin",
    "paymentIntent": "personal",              // personal or business
    "paymentProfileTokenType": "braintree",
    "paymentProfileUuid": "ac6b9149-...",     // from whoami / getCheckoutPresentationV1
    "isNeutralZoneEnabled": true,
    "isScheduledOrder": false,                // true for scheduled delivery
    "orderTotalFare": 8144000,                // amountE5 — $81.44
    "orderCurrency": "USD",
    "verticalLabel": "GROCERY",               // GROCERY, RESTAURANT, etc.
    "checkoutType": "drafting",
    "cookieConsent": true
  },
  "currentEaterConsent": {
    "defaultOptIn": false,
    "eaterConsented": false,
    "orgUUID": "94784998-..."                 // store's org UUID
  },
  "newEaterConsented": false,
  "isGroupOrder": false,
  "bypassAuthDeclineForTrustedUser": false,
  "checkoutActionResultParams": {
    "value": "{\"checkoutSessionUUID\":\"...\",\"useCaseKey\":\"...\",\"actionResults\":[],\"estimatedPaymentPlan\":{\"defaultPaymentProfile\":{\"paymentProfileUUID\":\"ac6b9149-...\",\"currencyAmount\":{\"amountE5\":8144000,\"currencyCode\":\"USD\"}},\"useCredits\":true}}"
  },
  "skipOrderRequestedEvent": false
}
```

**Key fields:**
- `draftOrderUUID` — the cart (from add_to_cart / createDraftOrderV2)
- `extraParams.storeUuid` — which store
- `extraParams.paymentProfileUuid` — payment method UUID (from whoami or getCheckoutPresentationV1)
- `extraParams.orderTotalFare` — total in amountE5 (multiply by 10^-5 for dollars)
- `extraParams.orderCurrency` — ISO 4217
- `extraParams.isScheduledOrder` — false for ASAP, true for scheduled
- `checkoutActionResultParams.value` — JSON string with checkout session UUID and payment plan (from getCheckoutPresentationV1)
- `extraParams.verticalLabel` — "GROCERY" for grocery stores, "RESTAURANT" for restaurants

**Response:** Redirects to order tracking page at `/orders/{uuid}?entryPoint=checkout`

**After checkout, these endpoints become active:**
- `getActiveOrdersV1` — live tracking with ETA, progress, map, courier (null until assigned)
- `getOrderEntityByUuidV1` — structured item data with fulfillment states (PENDING → FOUND/REPLACED/NOT_FOUND)

**Key insight:** The Eats API is NOT GraphQL — it's protobuf-style RPC over JSON at `/_p/api/`. The `_p` likely stands for "protobuf" or "protocol". All endpoints follow the pattern `{verb}{Entity}V{version}`. This is a stable, versioned API surface.

**Completed order items:** `getOrderEntityByUuidV1` and `getOrderEntitiesV1` both return 404/null for completed orders — they only work during active delivery. For completed order history, `getReceiptByWorkflowUuidV1` is the **only** path to item-level data. The HTML is stable (uses `data-testid` attributes) and parseable with lxml. Per-item prices are empty on completed orders, but totals/fees are always present.

**Active order items:** During a live delivery, `getOrderEntityByUuidV1` should return structured JSON item data (untested — need a live order). This will be the Phase 2 path.

### Reorder mechanism — draft orders carry catalog UUIDs (discovered 2026-04-02)

**Key discovery:** When the browser navigates to `/orders/{uuid}`, Uber auto-creates a draft order
(`createDraftOrderV2`) containing all items from that past order, mapped to their **current catalog
UUIDs** with section/subsection UUIDs, prices, and images. This is the reorder mechanism.

The draft order items have `uuid` fields that are **catalog product UUIDs** (NOT order-line UUIDs).
These match the UUIDs from `getStoreV1` exactly. No fuzzy name matching needed.

**Flow:**
1. `getPastOrdersV1` → get order UUID
2. Visit `/orders/{uuid}` (or call the endpoint that auto-creates the reorder draft)
3. `getDraftOrdersByEaterUuidV1` → find the new draft for the same store
4. `getDraftOrderByUuidV2` → read cart items with catalog UUIDs
5. Items have: `uuid` (catalog), `sectionUuid`, `subsectionUuid`, `title`, `price`, `imageURL`, `quantity`

**Draft order item shape (from getDraftOrderByUuidV2):**
```json
{
  "shoppingCartItemUuid": "...",      // per-line UUID (client-generated)
  "uuid": "67017397-fbe2-...",        // CATALOG PRODUCT UUID — matches getStoreV1
  "storeUuid": "c928e271-...",
  "sectionUuid": "f0faacd4-...",
  "subsectionUuid": "b71a1b81-...",
  "title": "Dole Organic Bananas",
  "price": 277,                       // cents
  "imageURL": "https://tb-static...",
  "quantity": 1,
  "fulfillmentIssueAction": {...},
  "customizations": [...]
}
```

**Important:** Receipt item UUIDs (from `getReceiptByWorkflowUuidV1` data-testid attributes) are
order-line-item UUIDs — NOT catalog UUIDs. They live in a different ID space. Only the draft
order / shopping cart items carry catalog UUIDs that join with `getStoreV1` products.

**Reorder mechanism confirmed (2026-04-02):** The "Reorder" button on `/orders` calls
`createDraftOrderV2` with ALL past order items pre-populated in `shoppingCartItems[]`. Each item
has its catalog UUID, store UUID, section UUIDs, prices, quantities, and customizations. The
browser resolves the past-order→catalog-UUID mapping client-side from React state data.

There is also a `createDraftOrderByOrderUuidV1` endpoint in the JS bundles, but it returns 400
with all param shapes we tried. The browser doesn't use it — it uses the standard `createDraftOrderV2`
with items inline.

**For API-based reorder:** Call `getStoreV1` to get current catalog UUIDs, match past order item
names to catalog products (name normalization), then call `createDraftOrderV2` with `shoppingCartItems[]`
containing catalog UUIDs. This is exactly what the browser does — it just has the mapping cached.

### `getStoreV1` — store details + full product catalog (captured 2026-04-02)

The key endpoint for browsing store products. Returns store metadata AND the entire product catalog in one call.

```json
// Request
{ "storeUuid": "c928e271-ee69-5eba-b331-3756bd2f5345" }

// Response shape (91 top-level keys)
{
  "status": "success",
  "data": {
    "title": "Costco Wholesale",
    "uuid": "c928e271-ee69-5eba-b331-3756bd2f5345",
    "isOpen": true,
    "isOrderable": true,
    "etaRange": { "text": "66–66 Min" },
    "rating": { "ratingValue": 4.8, "reviewCount": "4000+" },
    "categories": [...],           // category links for navigation
    "catalogSectionsMap": {        // THE PRODUCT CATALOG
      "<section-uuid>": [
        {
          "type": "HORIZONTAL_GRID",  // or "EATER_MESSAGE" (skip these)
          "catalogSectionUUID": "<uuid>",
          "payload": {
            "type": "standardItemsPayload",
            "standardItemsPayload": {
              "title": { "title": "Section Name" },
              "catalogItems": [
                {
                  "title": "Kirkland Signature Rotisserie Chicken",
                  "uuid": "c526b0a6-625d-5b65-b84b-e394a9b7aef2",
                  "price": 539,              // CENTS — divide by 100 for dollars
                  "imageUrl": "https://tb-static.uber.com/...",
                  "itemDescription": "...",
                  "isAvailable": true,
                  "hasCustomizations": false,  // true for items with size/options
                }
              ]
            }
          }
        }
      ]
    }
  }
}
```

**Key facts about `getStoreV1`:**
- Returns the FULL catalog — no pagination needed (165 items for Costco Austin)
- Prices are in cents (fractional — e.g. `538.92` = $5.39). Some have rounding artifacts.
- Items appear in multiple sections (e.g. Rotisserie Chicken appears 4x in different categories)
- `type: "EATER_MESSAGE"` items are promotional banners — skip them
- `type: "HORIZONTAL_GRID"` items contain actual products in `payload.standardItemsPayload.catalogItems`
- Store UUID can come from `list_deliveries` (past orders) or `getSearchHomeV2` / `getFeedV1` (browsing)
- Only needs `x-csrf-token: x` header + cookies (browser UA injected by engine for cookie-auth)

**Item fields:**

| Field | Type | Notes |
|-------|------|-------|
| `title` | string | Product name with size/count |
| `uuid` | string | Item UUID — used for `addItemsToDraftOrderV2` |
| `price` | number | Cents (fractional). Divide by 100. |
| `imageUrl` | string | Product image URL |
| `itemDescription` | string | Longer description |
| `isAvailable` | boolean | Whether item can be ordered now |
| `hasCustomizations` | boolean | Whether item has size/option variants |

**Costco Austin sample (165 items, 11 sections):**
- Rotisserie Chicken $5.39
- Organic Bananas $2.37
- Kirkland Smoked Salmon $25.91
- Kirkland Cashews $21.59
- Fresh Chicken Breast $23.22
- Wild Sockeye Salmon Fillet $18.12
- Fairlife Protein Shake 18-pack $43.19

#### `getMenuItemV1` — item customization options (captured 2026-04-05)

Returns all customization groups and options for a menu item. This is the key endpoint for adding toppings, sizes, sides, etc.

```json
// Request
{
  "itemRequestType": "ITEM",
  "storeUuid": "92faf8b2-ad6f-5126-b45c-f5a3f89deb86",
  "sectionUuid": "c6164ff2-ca35-5432-9113-bc3aee79604a",
  "subsectionUuid": "0379a62a-1156-4ddb-a09a-7e1dc45d5dfb",
  "menuItemUuid": "b003f5fe-8a16-563b-98d9-a43ea5d6817d",
  "cbType": "EATER_ENDORSED",
  "includeCheaperAlternatives": false,
  "contextReferences": [
    {"type": "GROUP_ITEMS", "payload": {"type": "groupItemsContextReferencePayload", "groupItemsContextReferencePayload": {}}, "pageContext": "UNKNOWN"}
  ]
}

// Response (key fields)
{
  "status": "success",
  "data": {
    "customizationsList": [
      {
        "uuid": "016cb9f9-...",      // customization group UUID
        "title": "Whole",             // group name
        "groupId": 0,                 // integer group index
        "minPermitted": 0,            // 0 = optional
        "maxPermitted": 15,           // max selections in this group
        "options": [
          {
            "uuid": "95bbd11d-...",   // option UUID
            "title": "Pepperoni",
            "price": 400,             // cents — $4.00
            "minPermitted": 0,
            "maxPermitted": 15,       // max quantity of this option
            "defaultQuantity": 0,
            "isSoldOut": false,
            "childCustomizationList": []  // nested customizations (e.g. half toppings)
          }
        ]
      }
    ]
  }
}
```

**Sammataro Classic Pie customization groups (2026-04-05):**

| Group | Title | Options | Price range |
|-------|-------|---------|-------------|
| 0 | Whole | 15 toppings: Pepperoni $4, Sausage $4, Mushroom $3, Ricotta $3, ... | $3–$4 |
| 1 | Half Toppings | 1ST HALF / 2ND HALF, each with 7 child toppings | $2.25–$2.50 |

**Customization format in cart requests:**

The `customizations` field in `createDraftOrderV2` / `addItemsToDraftOrderV2` uses this key format:
```
Key: "{customizationGroupUuid}+{groupId}"
Value: array of selected option objects
```

Example — adding Pepperoni as a whole topping:
```json
"customizations": {
  "016cb9f9-9ead-5880-a57c-431350775a71+0": [
    {
      "uuid": "95bbd11d-82ee-51df-a50f-f40d08500bbc",
      "price": 400,
      "quantity": 1,
      "title": "Pepperoni",
      "defaultQuantity": 0,
      "customizationMeta": {
        "title": "Whole",
        "isPickOne": false
      }
    }
  ]
}
```

**Nested customizations (half toppings):**
```json
"6a37054e-c34b-562a-986a-7f7caabbe815+1": [
  {
    "uuid": "8755bdb8-...",
    "price": 0,
    "quantity": 1,
    "title": "1ST HALF",
    "customizationMeta": {"title": "Half Toppings", "isPickOne": false},
    "childCustomizations": {
      "5005c439-90d3-54e5-af16-cf2b1f4f7b29+0": [
        {"uuid": "5ac3cad4-...", "price": 225, "quantity": 1, "title": "Sausage", ...}
      ]
    }
  }
]
```

**Quantity:** The `quantity` field on cart items already supports values > 1 — tested with `quantity: 2` successfully. The API returns `itemQuantity.inSellableUnit.value.coefficient: 2`.

**Required fields from `getStoreV1` for `getMenuItemV1`:**
- `storeUuid` — store UUID
- `sectionUuid` — from the item's `_raw.sectionUuid`
- `subsectionUuid` — from the item's `_raw.subsectionUuid`
- `menuItemUuid` — from the item's `uuid`

All four UUIDs are already preserved in the `_raw` field that `get_store` attaches to each product.

#### `getInStoreSearchV1` — in-store product search (captured 2026-04-05)

Used by `search_products` operation. Returns items matching a search query within a specific store.

```json
// Request
{
  "storeUuid": "92faf8b2-...",
  "query": "pepperoni"
}

// Response
{
  "status": "success",
  "data": {
    "sections": [
      {
        "catalogSectionUUID": "c6164ff2-...",
        "title": { "title": "Results" },
        "catalogItems": [...]          // same shape as getStoreV1 catalogItems
      }
    ]
  }
}
```

### Next steps

1. ~~Call `getOrderEntityByUuidV1`~~ **Done** — only works for active orders, 404 for completed
2. ~~Add Eats connection~~ **Done** — `.ubereats.com` in skill.yaml
3. **Build `list_deliveries`** — backed by `getPastOrdersV1`
4. **Build `get_delivery`** — backed by `getReceiptByWorkflowUuidV1` (items via HTML) + `getPastOrdersV1` (metadata)
5. **Capture Costco store page** — `browse capture` on a Costco store URL to discover `getStoreV1` and menu endpoints
6. **Build `list_stores`** — backed by `getFeedV1` or `getPaginatedStoresV1`
7. **Test `getOrderEntityByUuidV1` during a live order** — may return structured items for Phase 2

### Agent DX notes

**CDP authenticated requests:** To call Uber Eats API endpoints through CDP:
1. Browser must be on an `ubereats.com` page (CORS — `credentials: 'include'` only sends cookies for same-origin)
2. Navigate first: `Page.navigate` to `https://www.ubereats.com/`, wait ~5s
3. Use `Runtime.evaluate` with an async IIFE that calls `fetch()` — cookies are sent automatically
4. The `x-csrf-token: x` header is required, other headers (session-id, location, etc.) are optional for basic reads

**Cookie encryption:** Brave's SQLite cookie DB stores encrypted values (`encrypted_value` column). You cannot extract cookies by reading the DB directly — use CDP `Network.getCookies` or the agentOS engine's auth resolver instead.

**Python websocket library:** Use `websocket` (installed), NOT `websockets` (not installed). Import: `import websocket`, then `websocket.create_connection(url)`. Synchronous API — no asyncio needed.
