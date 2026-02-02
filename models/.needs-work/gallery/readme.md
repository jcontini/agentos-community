# Gallery App

Displays photos, albums, and image collections.

## Capabilities

| Capability | Description |
|------------|-------------|
| `photo_list` | List photos from library/album |
| `photo_get` | Get full photo details with EXIF |

---

## Schemas

### `photo_list`

```typescript
// Input
{
  album_id?: string,
  date_from?: string,        // YYYY-MM-DD
  date_to?: string,
  people?: string[],         // filter by people in photo → links to contacts
  location?: string,         // place name or coordinates
  limit?: number
}

// Output
{
  photos: {
    id: string               // required
    filename: string
    url: string              // required (thumbnail or full)
    thumbnail_url?: string
    timestamp: string        // required (when taken)
    width: number
    height: number
    size?: number            // bytes
    mime_type?: string
    album?: {
      id: string
      name: string
    }
    // EXIF data
    location?: {
      latitude: number
      longitude: number
      place_name?: string    // reverse geocoded
    }
    camera?: {
      make?: string          // "Apple"
      model?: string         // "iPhone 15 Pro"
    }
    settings?: {
      aperture?: string      // "f/1.8"
      shutter_speed?: string // "1/120"
      iso?: number
      focal_length?: string
    }
    // People
    people?: {               // → links to contact_get
      id?: string            // contact ID if matched
      name: string
      bounds?: { x: number, y: number, width: number, height: number }
    }[]
    is_favorite?: boolean
  }[]
}
```

### `photo_get`

Get full photo details.

```typescript
// Input
{ id: string }

// Output - same as photo_list item with full EXIF
```

---

## Cross-References

| Field | Links to |
|-------|----------|
| `people[].id` | `contact_get(id)` |
| `location` | Map view |
| `album` | `collection_get(item_type: 'photo')` |

---

## Example Connectors

- **Apple Photos** — macOS/iOS photo library
- **Google Photos** — Google cloud photos
- **iCloud Photos** — Apple cloud storage
