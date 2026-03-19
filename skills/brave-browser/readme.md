# Brave Browser

Access browsing history, bookmarks, cookies, and session credentials from Brave Browser's local databases.

Brave is Chromium-based, so it uses the same cookie encryption scheme as Chrome:
AES-128-CBC with a key derived via PBKDF2 from a master password stored in macOS Keychain.

## Requirements

- **macOS only** — reads local SQLite databases
- **Brave Browser installed** — databases must exist at the standard paths
- **Full Disk Access** — System Settings > Privacy & Security > Full Disk Access (for the process reading the databases)
- **Brave closed (for cookies)** — SQLite WAL lock; or use `cookie_get` which copies to `/tmp`

## Data Sources

```
History  ~/Library/Application Support/BraveSoftware/Brave-Browser/Default/History
Cookies  ~/Library/Application Support/BraveSoftware/Brave-Browser/Default/Cookies
```

## Cookie Decryption

Brave encrypts cookie values on macOS using:
1. A master password stored in macOS Keychain under `"Brave Safe Storage"` / account `"Brave"`
2. PBKDF2-HMAC-SHA1 (salt: `saltysalt`, 1003 iterations, 16-byte key)
3. AES-128-CBC (IV: 16 space bytes = `20` repeated 16 times in hex)
4. The encrypted value has a 3-byte `v10` prefix that must be stripped before decryption

The `get_cookie_key` operation handles steps 1-2. The `cookie_get` operation does the full pipeline.

## Cookie Extraction

Extract decrypted cookies for any domain. Consumed through cookie provider matchmaking at runtime.

```
use({ skill: "brave-browser", tool: "cookie_get", params: { domain: ".claude.ai", names: "sessionKey" } })
→ { domain: ".claude.ai", cookies: [{name: "sessionKey", value: "sk-ant-...", httpOnly: true, ...}], count: 1 }

use({ skill: "brave-browser", tool: "cookie_get", params: { domain: ".chase.com" } })
→ { domain: ".chase.com", cookies: [...], count: 5 }
```

## Operations

```
OPERATION          DESCRIPTION
--------------     -------------------------------------------------------
list_webpages      Recently visited pages from Brave history
search_webpages    Search browsing history by URL or title

OPERATION          DESCRIPTION
--------------     -------------------------------------------------------
list_accounts      List Brave profiles with display names
get_cookie_key     Derive AES-128 key from Keychain (PBKDF2)
list_cookies       List raw (encrypted) cookies for a domain
cookie_get         Full pipeline: extract + decrypt any cookies for a domain
```
