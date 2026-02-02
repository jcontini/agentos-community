# Email App

Displays email inbox, threads, and message composition.

## Capabilities

| Capability | Description |
|------------|-------------|
| `email_list` | List emails from inbox/folder |
| `email_get` | Get full email with body |
| `email_thread` | Get conversation thread |

---

## Schemas

### `email_list`

```typescript
// Input
{
  folder?: 'inbox' | 'sent' | 'drafts' | 'archive' | 'trash' | string,
  from?: string,              // filter by sender
  to?: string,                // filter by recipient
  query?: string,             // search subject/body
  unread_only?: boolean,
  has_attachment?: boolean,
  after?: string,             // date filter
  before?: string,
  limit?: number
}

// Output
{
  emails: {
    id: string               // required
    thread_id?: string       // for grouping conversations
    subject: string          // required
    snippet?: string         // preview text
    from: {                  // required
      name?: string
      email: string          // → can link to contact_list
    }
    to: {
      name?: string
      email: string
    }[]
    cc?: { name?: string, email: string }[]
    timestamp: string        // required (ISO datetime)
    is_read: boolean
    is_starred?: boolean
    has_attachments: boolean
    labels?: string[]        // Gmail-style labels/tags
    folder?: string
  }[]
}
```

### `email_get`

Get full email with body and attachments.

```typescript
// Input
{ id: string }

// Output
{
  id: string                 // required
  thread_id?: string
  subject: string            // required
  from: { name?: string, email: string }
  to: { name?: string, email: string }[]
  cc?: { name?: string, email: string }[]
  bcc?: { name?: string, email: string }[]
  reply_to?: { name?: string, email: string }
  timestamp: string          // required
  body_text?: string         // plain text version
  body_html?: string         // HTML version
  is_read: boolean
  is_starred?: boolean
  labels?: string[]
  attachments?: {
    id: string
    filename: string
    mime_type: string
    size: number             // bytes
    url?: string             // download URL
  }[]
  in_reply_to?: string       // parent email ID
  references?: string[]      // email thread chain
}
```

### `email_thread`

Get full email conversation thread.

```typescript
// Input
{ thread_id: string }

// Output
{
  thread_id: string          // required
  subject: string
  participants: { name?: string, email: string }[]
  messages: Email[]          // same structure as email_get
  message_count: number
}
```

---

## Cross-References

| Field | Links to |
|-------|----------|
| `from.email` | `contact_list(search: email)` |
| `to[].email` | `contact_list(search: email)` |
| `attachments[].url` | file download / `web_read` |
| `labels[]` | `collection_list(item_type: 'email')` |

---

## Example Connectors

- **Gmail** — Google email
- **Mimestream** — Native macOS email client
- **Outlook** — Microsoft 365 email
- **Apple Mail** — macOS/iOS email
- **Fastmail** — Privacy-focused email
