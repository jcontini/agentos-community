# Apple

Access macOS Calendar and Contacts via native APIs.

## Requirements

- **macOS only**
- **Permissions required** in System Settings → Privacy & Security:
  - Calendars → Full Access
  - Contacts → Allow

### Granting Permissions

1. Open **System Settings → Privacy & Security**
2. Click **Calendars** (or **Contacts**)
3. Enable access for the app (Cursor, Terminal, etc.)
4. Restart the app if needed

## Tools

| Tool | Implementation | Notes |
|------|----------------|-------|
| Calendar | EventKit (Swift binary) | Full CRUD, attendees, recurrence |
| Contacts | SQL reads + AppleScript writes | Full CRUD, photos |

## Why This Architecture?

### Calendar: EventKit

AppleScript calendar access is limited:
- Can't handle async permission prompts (macOS 14+)
- Recurrence rules are difficult to parse
- No attendee access
- Slow for large calendars

EventKit provides full access via a compiled Swift helper binary.

### Contacts: AppleScript

The Contacts framework (`CNContact`) has known bugs:
- `mutableCopy()` doesn't preserve notes
- Social profiles get corrupted
- Unreliable iCloud sync

AppleScript is Apple's canonical interface - changes sync reliably with iCloud.
SQLite is used for reads (fast, indexed) while AppleScript handles writes.

## Calendar Features

- List events with date range, calendar filter, search
- Get event details including attendees and recurrence
- Create events (timed or all-day)
- Update events (title, time, location, calendar)
- Delete events
- List all calendars

## Contacts Features

- Search/list contacts
- Get full contact details (all phones, emails, URLs)
- Create contacts with auto-normalization
- Update contact fields
- Delete contacts
