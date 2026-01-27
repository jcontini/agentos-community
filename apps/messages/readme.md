# Messages App

Displays conversations, chats, and direct messages.

## Capabilities

| Capability | Description |
|------------|-------------|
| `message_list` | List conversations |
| `message_get` | Get messages in a thread |
| `message_send` | Send a message |

---

## Entity Display Names

| Connector | Display Name |
|-----------|-------------|
| iMessage | Message / Text |
| WhatsApp | Message / Chat |
| Slack | Message / DM |
| Discord | Message / DM |
| Telegram | Message |

---

## Schemas

### `message_list`

```typescript
// Input
{ contact?: string, limit?: number, unread_only?: boolean }

// Output
{
  conversations: {
    thread_id: string        // required
    title?: string           // group name or participant names
    
    // === Group vs 1:1 ===
    is_group: boolean        // true = group chat, false = 1:1
    participant_count: number
    participants: {          // → can link to contact_get
      id?: string            // contact ID if matched
      name: string           // required
      phone?: string
      email?: string
      avatar?: string
      role?: 'owner' | 'admin' | 'member'  // for groups
      is_me?: boolean        // true if this is the user
    }[]
    
    // === Group metadata ===
    group?: {
      icon?: string          // group avatar/photo
      created_at?: string
      created_by?: string    // participant name
      description?: string
    }
    
    // === Last message preview ===
    last_message: {
      content: string
      timestamp: string
      sender: string
      is_me?: boolean
    }
    
    // === Status ===
    unread_count?: number
    is_muted?: boolean
    is_pinned?: boolean
    is_archived?: boolean
    
    // === Provider ===
    provider?: 'imessage' | 'whatsapp' | 'telegram' | 'signal' | 'messenger' | 'slack' | 'discord'
  }[]
}
```

### `message_get`

```typescript
// Input
{ thread_id: string, limit?: number, before?: string }

// Output
{
  thread_id: string          // required
  is_group: boolean
  title?: string
  
  participants: {
    id?: string
    name: string             // required
    avatar?: string
    role?: 'owner' | 'admin' | 'member'
    is_me?: boolean
  }[]
  
  messages: {
    id: string               // required
    sender: {
      name: string           // required
      avatar?: string
      is_me?: boolean
    }
    content: string          // required
    timestamp: string        // required
    
    // === Delivery/Read status ===
    status?: 'sending' | 'sent' | 'delivered' | 'read' | 'failed'
    read_by?: {              // for groups: who has read this message
      name: string
      read_at: string
    }[]
    delivered_at?: string
    read_at?: string         // for 1:1 chats
    
    // === Replies/Threading ===
    reply_to?: {             // if this is a reply to another message
      id: string
      content: string        // preview of original
      sender: string
    }
    
    // === Reactions/Tapbacks ===
    reactions?: {
      emoji: string          // "👍", "❤️", "😂", etc.
      count: number
      users?: string[]       // who reacted
      includes_me?: boolean
    }[]
    
    // === Attachments ===
    attachments?: {
      type: 'image' | 'video' | 'audio' | 'file' | 'link' | 'location' | 'contact' | 'sticker'
      url?: string           // → link can go to web_read
      thumbnail?: string
      name?: string
      size?: number
      duration_ms?: number   // for audio/video
      mime_type?: string
      // For location
      location?: {
        lat: number
        lng: number
        name?: string
      }
      // For shared contact
      contact?: {
        name: string
        phone?: string
      }
    }[]
    
    // === Special message types ===
    is_system?: boolean      // "John added Jane to the group"
    system_event?: 'member_added' | 'member_removed' | 'group_created' | 
                   'group_renamed' | 'icon_changed' | 'call_started' | 'call_ended'
    
    // === Editing ===
    edited_at?: string
    is_deleted?: boolean
  }[]
  
  // Pagination
  has_more: boolean
}
```

### `message_send`

```typescript
// Input
{
  thread_id?: string,        // existing conversation (omit for new)
  to?: string[],             // phone numbers/emails for new conversation
  content: string,
  attachments?: {
    type: 'image' | 'video' | 'audio' | 'file'
    url: string              // file URL to attach
  }[],
  reply_to?: string          // message ID to reply to
}

// Output
{
  id: string                 // new message ID
  thread_id: string          // conversation ID (new or existing)
  status: 'sent' | 'queued' | 'failed'
  timestamp: string
}
```

---

## Cross-References

| Field | Links to |
|-------|----------|
| `participants[].id` | `contact_get(id)` |
| `attachments[].url` (link type) | `web_read(url)` |

---

## Example Connectors

- **iMessage** — Apple Messages
- **WhatsApp** — Meta messaging
- **Telegram** — Cloud-based messaging
- **Signal** — Privacy-focused messaging
- **Slack** — Team communication
- **Discord** — Community chat
