# Gmail Skill — Requirements & Protocol Reference

## Connections

### 1. `gmail` — OAuth (REST API)
- Base: `https://gmail.googleapis.com/gmail/v1/users/me`
- Auth: OAuth token via Mimestream provider (or any Google OAuth provider)
- Scope: `https://mail.google.com/`
- Stable, documented API. Primary path for reads and writes.

### 2. `sync` — Cookie auth (Gmail web protocol)
- Base: `https://mail.google.com`
- Auth: Google session cookies from browser (SID, HSID, SSID, OSID)
- Used for internal Gmail operations not in the public API (e.g. unsubscribe state)
- Can also be used as fallback for reads when OAuth is unavailable

### 3. Future: `macos` — macOS Google account
- Could provide OAuth tokens with broader scopes (Contacts, Calendar, Gmail)
- via macOS Accounts framework or Keychain
- Would eliminate Mimestream dependency

## Gmail Web Protocol (sync endpoints)

Reverse-engineered via CDP capture 2026-04-02.

### Endpoints

| Path | Purpose |
|------|---------|
| `/sync/u/0/i/s` | Sync/poll — check for new emails, apply labels, unsubscribe |
| `/sync/u/0/i/bv` | Batch view — load inbox/label views (bulk email list) |
| `/sync/u/0/i/fd` | Full detail — fetch complete thread when opening an email |

Action operations use POST with `act` parameter codes:
- `sm` = send message
- `tr` = trash/delete
- `sp` = mark as spam
- `st` = star
- `rc_^i` = archive

### Authentication (3 layers)

**Layer 1: Session cookies (reads)**
Only 4 cookies needed: `SID`, `HSID`, `SSID`, `OSID`
- Work across machines, IPs, browsers
- Persist until explicit logout (~2 year lifetime)
- Sufficient for read operations

**Layer 2: SAPISIDHASH (writes)**
Required for mutating operations. Header format:
```
Authorization: SAPISIDHASH <timestamp>_<SHA1(timestamp + " " + SAPISID_cookie + " " + origin)>
```
Where origin = `https://mail.google.com`. Needs the `SAPISID` cookie value.

**Layer 3: Page-embedded tokens**
- `ik` — per-user constant (interaction key), embedded in page HTML
- `at` — XSRF token, included as URL parameter in POSTs

### Wire Format: PbLite

Google's JSON-array serialization of Protocol Buffers:
- Field N occupies array index N (1-indexed)
- Nested messages are recursive arrays
- `null` = unset field
- Booleans as `1`/`0`
- Response prefix: `)]}'\n` (anti-JSON-hijacking)
- Content-Type: `application/json+protobuf`

### Internal Labels (discovered)

| Label | Meaning |
|-------|---------|
| `^punsub` | User unsubscribed from this sender |
| `^punsub_sat` | Unsubscribe was satisfied (POST succeeded) |
| `^oc_unsub` | Unsubscribe recorded |
| `^p_mtunsub` | Mail-type unsubscribe |
| `^smartlabel_promo` | CATEGORY_PROMOTIONS |
| `^smartlabel_notification` | CATEGORY_UPDATES |
| `^smartlabel_social` | CATEGORY_SOCIAL |
| `^smartlabel_group` | CATEGORY_FORUMS |

### Stability Warning

Gmail's web protocol has no stability guarantees. gmail.js (5k stars) requires
constant maintenance. The PbLite wire format changes without notice. The REST API
(OAuth connection) should remain the primary path for stability; the sync protocol
is for operations the REST API doesn't support and as a fallback.

### Engine Compatibility

The agentOS HTTP engine fully supports Gmail web protocol:
- `cookies=` parameter passes raw cookie string as Cookie header
- `headers=` supports arbitrary headers including `Authorization: SAPISIDHASH`
- `http.client()` sessions maintain cookie jars across requests
- `wreq` TLS fingerprint matches Chrome (BoringSSL)
- No domain restrictions, no CORS enforcement

### Open Source References

- [gmail.js](https://github.com/KartikTalwar/gmail.js) — browser-side Gmail protocol hooks
- [gmail-cookies-research](https://github.com/CoalDev/gmail-cookies-research) — 4-cookie read access
- [hangups pblite.py](https://github.com/tdryer/hangups/blob/master/hangups/pblite.py) — PbLite encoder/decoder
- [SAPISIDHASH algorithm](https://gist.github.com/eyecatchup/2d700122e24154fdc985b7071ec7764a)
