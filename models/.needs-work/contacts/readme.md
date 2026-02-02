# Contacts App

Displays contact cards, address books, and people information.

## Capabilities

| Capability | Description |
|------------|-------------|
| `contact_list` | List contacts with search |
| `contact_get` | Get full contact details |

---

## Schemas

### `contact_list`

```typescript
// Input
{ search?: string, organization?: string, limit?: number }

// Output (lightweight for list view)
{
  contacts: {
    id: string               // required
    first_name?: string
    last_name?: string
    display_name: string     // required (computed: "First Last" or org)
    organization?: string
    job_title?: string
    phones?: string          // comma-separated for list view
    emails?: string          // comma-separated for list view
    has_photo?: boolean
    modified_at?: string
  }[]
}
```

### `contact_get`

```typescript
// Input
{ id: string }

// Output (full detail with arrays)
{
  id: string                 // required
  first_name?: string
  last_name?: string
  middle_name?: string
  nickname?: string
  display_name: string       // required
  organization?: string
  job_title?: string
  department?: string
  birthday?: string          // YYYY-MM-DD
  notes?: string
  has_photo?: boolean
  phones: {                  // array with labels
    label: string            // "mobile", "work", "home"
    value: string
  }[]
  emails: {
    label: string
    value: string
  }[]
  urls: {                    // → can link to web_read
    label: string
    value: string            // URL
  }[]
  addresses: {
    label: string
    street?: string
    city?: string
    state?: string
    postal_code?: string
    country?: string
  }[]
}
```

---

## Cross-References

| Field | Links to |
|-------|----------|
| `urls[].value` | `web_read(url)` |
| `emails[].value` | `email_list(contact)` |

---

## Example Connectors

- **Apple Contacts** — macOS/iOS address book
- **Google Contacts** — Google account contacts
- **LinkedIn** — Professional network (read-only)
