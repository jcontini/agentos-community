# Products App

Displays products, wishlists, carts, and orders.

## Capabilities

| Capability | Description |
|------------|-------------|
| `product_list` | List products by status/collection |
| `product_get` | Get full product/order details |

---

## Design Philosophy

A "product" is the core entity. Collections of products represent different states:
- **Wishlist** — `Collection<product>` with status "want"
- **Cart** — `Collection<product>` with status "cart"
- **Order** — `Collection<product>` with status "ordered/shipped/delivered" + totals, shipping, tracking

This parallels how `book_list` has `shelf: 'want' | 'reading' | 'read'`.

---

## Schemas

### `product_list`

```typescript
// Input
{
  status?: 'wishlist' | 'cart' | 'ordered' | 'shipped' | 'delivered' | 'returned' | 'all',
  store?: string,            // filter by seller/store
  collection_id?: string,    // specific wishlist/order
  after?: string,            // date filter YYYY-MM-DD
  before?: string,
  limit?: number
}

// Output
{
  products: {
    id: string               // required
    name: string             // required
    description?: string
    url?: string             // → web_read (product page)
    image?: string           // thumbnail
    
    // === Pricing ===
    price: number            // required (current/purchase price)
    original_price?: number  // if on sale
    currency: string         // "USD", "EUR"
    
    // === Status ===
    status: 'wishlist' | 'cart' | 'ordered' | 'shipped' | 'delivered' | 'returned'
    quantity?: number        // for cart/orders
    variant?: string         // "Size: M, Color: Blue"
    
    // === Store/Seller ===
    store: {
      name: string           // required "Amazon", "Apple Store"
      url?: string           // → web_read
      logo?: string
    }
    
    // === Order metadata (when status is ordered+) ===
    order?: {
      id: string             // order ID/number
      order_number: string   // human-readable "112-3456789-0123456"
      order_date: string     // when ordered
      delivery_date?: string // actual or estimated
    }
    
    // === Tracking (when shipped) ===
    tracking?: {
      number: string
      carrier: string        // "UPS", "FedEx", "USPS"
      url?: string           // tracking page → web_read
      status?: string        // "In Transit", "Out for Delivery"
      estimated_delivery?: string
    }
    
    // === Collection context ===
    collection?: {
      id: string
      name: string           // "My Wishlist", "Order #123"
      type: 'wishlist' | 'cart' | 'order'
    }
    
    // === Timestamps ===
    added_at?: string        // when added to wishlist/cart
    purchased_at?: string    // when ordered
  }[]
}
```

### `product_get`

Get full product or order details.

```typescript
// Input
{ id: string }

// Output
{
  // ... all fields from product_list ...
  
  // === Extended product info ===
  brand?: string
  category?: string
  sku?: string
  upc?: string
  specifications?: Record<string, string>
  
  // === Order details (when applicable) ===
  order_details?: {
    totals: {
      subtotal: number
      tax?: number
      shipping?: number
      discount?: number
      total: number          // required
      currency: string
    }
    shipping_address?: {
      name: string
      street: string
      city: string
      state?: string
      postal_code: string
      country: string
    }
    payment?: {
      method: string         // "Visa", "PayPal", "Apple Pay"
      last_four?: string     // "4242"
    }
    timeline?: {             // order history
      timestamp: string
      status: string
      description?: string
    }[]
    invoice_url?: string
    return_by?: string       // return window deadline
  }
}
```

---

## Cross-References

| Field | Links to |
|-------|----------|
| `url` | `web_read(url)` (product page) |
| `store.url` | `web_read(url)` |
| `tracking.url` | `web_read(url)` (carrier tracking) |
| `collection` | `collection_get(item_type: 'product')` |

---

## Example Connectors

- **Amazon** — E-commerce (orders, wishlists)
- **Apple Store** — Apple purchases
- **eBay** — Auction/marketplace
- **Shopify** — Multi-store orders
- **Notion** — Product databases
