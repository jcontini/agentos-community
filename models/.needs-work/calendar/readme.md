# Calendar App

Displays events, schedules, and calendar views.

## Capabilities

| Capability | Description |
|------------|-------------|
| `event_list` | List upcoming/past events |
| `event_create` | Create a new event |

---

## Schemas

### `event_list`

```typescript
// Input
{ 
  days?: number,             // days from today (default: 7)
  past?: boolean,            // look backward instead of forward
  calendar_id?: string,      // filter by calendar
  query?: string,            // search title/location/description
  exclude_all_day?: boolean
}

// Output (based on Apple Calendar schema)
{
  events: {
    id: string               // required
    title: string            // required
    start: string            // required (ISO datetime)
    end: string              // required (ISO datetime)
    all_day: boolean
    location?: string
    description?: string
    calendar: {              // nested object
      id: string
      name: string
      color?: string
    }
    attendees?: {            // → can link to contact_get by email
      name: string
      email?: string
      status: 'accepted' | 'declined' | 'tentative' | 'pending'
    }[]
    recurrence?: {
      rule: string           // RRULE description
    }
  }[]
}
```

### `event_create`

```typescript
// Input
{
  title: string,             // required
  start: string,             // required (YYYY-MM-DD HH:MM or YYYY-MM-DD)
  end?: string,              // defaults to 1 hour after start
  all_day?: boolean,
  location?: string,
  description?: string,
  calendar_id?: string
}

// Output
{
  id: string                 // required
  title: string              // required
  start: string              // required
  calendar: { name: string }
  status: 'created'
}
```

---

## Cross-References

| Field | Links to |
|-------|----------|
| `attendees[].email` | `contact_list(search: email)` |

---

## Example Connectors

- **Apple Calendar** — macOS/iOS calendar
- **Google Calendar** — Google account calendar
- **Outlook Calendar** — Microsoft 365 calendar
