# Apple Contacts

Access macOS Contacts as Person entities with multi-account support.

## Requirements

- **macOS only**
- **Permissions required** in System Settings → Privacy & Security → Contacts

## Multi-Account Support

macOS can have multiple contact accounts (iCloud, local, Exchange, etc.). Use the `accounts` utility to list available accounts and find the default one.

### Example Workflow

```
1. apple-contacts.accounts()  
   → Returns: [{id: "ABC-123", name: "iCloud", count: 500, is_default: true}, ...]

2. person.list(source: "apple-contacts", account: "ABC-123", limit: 10)
   → Returns: 10 most recently modified contacts as person entities
```

## Operations

| Operation | Description |
|-----------|-------------|
| `list_persons` | List contacts with phones, emails, organization |
| `get_person` | Get full details: addresses, notes, birthday |
| `search_persons` | Search contacts by name, email, phone, organization |

## Utilities

| Utility | Description |
|---------|-------------|
| `accounts` | List contact accounts (iCloud, local, work) |
| `create` | Create new contact |
| `update` | Update contact fields |
| `delete` | Delete contact |

## Architecture

| Operation | Executor | Notes |
|-----------|----------|-------|
| accounts | Swift helper | Lists contact containers |
| list/search | SQL | Fast indexed queries on AddressBook DB |
| get | Swift helper | Full details with structured arrays |
| create/update/delete | Swift helpers | Mutations with native Contacts APIs |
