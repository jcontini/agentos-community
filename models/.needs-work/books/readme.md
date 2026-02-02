# Books App

Displays reading lists, bookshelves, and book details.

## Capabilities

| Capability | Description |
|------------|-------------|
| `book_list` | List books by shelf/status |

---

## Schemas

### `book_list`

```typescript
// Input
{ shelf?: 'want' | 'reading' | 'read' | 'all', limit?: number }

// Output
{
  books: {
    id: string               // required
    title: string            // required
    author: string           // required
    isbn?: string            // for external enrichment
    cover?: string           // image URL
    status?: 'want' | 'reading' | 'read'
    rating?: number          // 0-5
    progress?: number        // 0-100 percent
    pages?: number
    url?: string             // link to source (Goodreads, Hardcover)
  }[]
}
```

---

## Cross-References

| Field | Links to |
|-------|----------|
| `url` | `web_read(url)` |
| `isbn` | External enrichment APIs |
| shelf | `collection_get(item_type: 'book')` |

---

## Related: Audiobooks

Audiobooks are handled by the **Player App** via `media_history` with `type: 'audiobook'`. The `media.book.isbn` field links audiobooks back to the book library.

---

## Example Connectors

- **Hardcover** — Modern book tracking
- **Goodreads** — Amazon-owned book community
- **Kindle** — Amazon e-reader library
- **Apple Books** — iOS/macOS reading
