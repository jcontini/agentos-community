---
id: brave-browser
name: Brave Browser
description: Browsing history, bookmarks, and cookies from Brave Browser on macOS — including session key extraction for claude.ai
icon: icon.svg
color: "#F83B1D"

website: https://brave.com
auth: none

connects_to: brave-browser-app

# Brave (Chromium-based) stores cookies encrypted in SQLite.
# The encryption key lives in macOS Keychain under "Brave Safe Storage" / "Brave".
# This skill exposes a credential_get utility that extracts and decrypts
# the sessionKey cookie for claude.ai, usable by consumer skills via provides:.
provides:
  - service: cookies
    description: "Extract decrypted cookies from Brave Browser's local database (including HttpOnly). Full Chromium cookie decryption pipeline."
    via: cookie_get
    account_param: domain
    accounts_via: list_accounts
    account_field: name

seed:
  - id: brave-browser-app
    types: [software]
    name: Brave Browser
    data:
      software_type: browser
      url: https://brave.com
      launched: "2016"
      platforms: [macos, windows, linux]
      pricing: free
    relationships:
      - role: offered_by
        to: brave-software

  - id: brave-software
    types: [organization]
    name: Brave Software, Inc.
    data:
      type: company
      url: https://brave.com
      founded: "2015"
      wikidata_id: Q50391972
# ==============================================================================
# TRANSFORMERS
# ==============================================================================

transformers:
  webpage:
    terminology: Page
    mapping:
      id: .url
      url: .url
      title: .title
      data: '{ visit_count: .visit_count }'

# ==============================================================================
# OPERATIONS
# ==============================================================================

operations:
  webpage.list:
    description: List recently visited pages from Brave browsing history
    returns: webpage[]
    params:
      limit:
        type: integer
        description: Maximum number of results
    sql:
      database: '"~/Library/Application Support/BraveSoftware/Brave-Browser/Default/History"'
      query: >
        SELECT url, title, visit_count,
               CAST((last_visit_time / 1000000) - 11644473600 AS INTEGER) AS last_visit_unix
        FROM urls
        WHERE hidden = 0
        ORDER BY last_visit_time DESC
        LIMIT :limit
      params:
        limit: '.params.limit // 1000'
      response:
        root: "/"

  webpage.search:
    description: Search Brave browsing history by URL or title
    returns: webpage[]
    params:
      query:
        type: string
        required: true
        description: Search term (matches URL and title)
      limit:
        type: integer
        description: Maximum number of results
    sql:
      database: '"~/Library/Application Support/BraveSoftware/Brave-Browser/Default/History"'
      query: >
        SELECT url, title, visit_count,
               CAST((last_visit_time / 1000000) - 11644473600 AS INTEGER) AS last_visit_unix
        FROM urls
        WHERE hidden = 0
          AND (url LIKE :query OR title LIKE :query)
        ORDER BY last_visit_time DESC
        LIMIT :limit
      params:
        query: '"%" + .params.query + "%"'
        limit: '.params.limit // 1000'
      response:
        root: "/"

# ==============================================================================
# UTILITIES
# ==============================================================================

utilities:
  list_accounts:
    description: List Brave browser profiles with their display name
    returns:
      name: string
      path: string
    command:
      binary: bash
      args:
        - "-l"
        - "-c"
        - |
          python3 -c "
          import json, os, glob
          base = os.path.expanduser('~/Library/Application Support/BraveSoftware/Brave-Browser')
          profiles = []
          for d in sorted(glob.glob(base + '/*/Preferences')):
              try:
                  with open(d) as f:
                      import json as j
                      prefs = j.load(f)
                  profile_dir = os.path.dirname(d)
                  name = prefs.get('profile', {}).get('name', os.path.basename(profile_dir))
                  email = prefs.get('profile', {}).get('user_name', '')
                  profiles.append({'name': name, 'email': email, 'path': profile_dir})
              except Exception:
                  pass
          print(json.dumps(profiles))
          "

  get_cookie_key:
    description: >
      Derive the AES-128 decryption key for Brave cookies on macOS.
      Reads the password from macOS Keychain ("Brave Safe Storage" / "Brave"),
      then runs PBKDF2-HMAC-SHA1 with salt "saltysalt" and 1003 iterations.
      Returns the hex-encoded 16-byte key.
    returns:
      key: string
    steps:
      steps:
        - id: get_password
          keychain:
            service: "Brave Safe Storage"
            account: "Brave"

        - id: derive_key
          crypto:
            algorithm: pbkdf2
            password: ".get_password.value"
            salt: "saltysalt"
            iterations: 1003
            key_length: 16

      response:
        mapping:
          key: ".derive_key.value"

  list_cookies:
    description: >
      List cookies for a domain from Brave's cookie database.
      Returns raw cookie data including hex-encoded encrypted values.
      Use get_cookie_key to get the decryption key, then decrypt individual
      values with the crypto executor (aes-128-cbc, IV = 20202020...x16).
      Brave encrypted_value starts with "hex:763130" (v10 prefix) — strip
      first 6 hex chars (3 bytes) before decrypting.
    returns:
      name: string
      host_key: string
      path: string
      encrypted_value: string
      is_secure: integer
      is_httponly: integer
      expires_utc: integer
    params:
      domain:
        type: string
        required: true
        description: Domain to get cookies for (e.g., "platform.claude.com")
      limit:
        type: integer
        description: Maximum number of cookies
    sql:
      database: '"~/Library/Application Support/BraveSoftware/Brave-Browser/Default/Cookies"'
      query: >
        SELECT name, host_key, path, hex(encrypted_value) as encrypted_value,
               is_secure, is_httponly, expires_utc
        FROM cookies
        WHERE host_key LIKE :domain
        ORDER BY name
        LIMIT :limit
      params:
        domain: '"%" + .params.domain + "%"'
        limit: '.params.limit // 1000'

  cookie_get:
    description: |
      Extract and decrypt cookies for a domain from Brave Browser's cookie database.
      Full decryption pipeline: Keychain → PBKDF2 → AES-128-CBC.
      Returns plaintext cookie values including HttpOnly cookies.
      This is the provider interface for cookie matchmaking — other skills
      that need browser cookies discover Brave through this utility.
    params:
      domain:
        type: string
        required: true
        description: "Cookie domain to match (e.g., '.claude.ai', '.chase.com')"
      names:
        type: string
        description: "Comma-separated cookie names to filter (e.g., 'sessionKey,csrf_token')"
      host:
        type: string
        description: "Specific host_key to match (more specific than domain, e.g., 'platform.claude.com')"
      profile:
        type: string
        description: "Brave profile directory name (default: 'Default')"
    returns:
      domain: string
      cookies: array
      count: integer
      source: string
    command:
      binary: python3
      args:
        - "/Users/joe/dev/agentos-community/skills/brave-browser/get-cookie.py"
        - "--domain"
        - ".params.domain"
        - if .params.names then "--names" else "" end
        - if .params.names then .params.names else "" end
        - if .params.host then "--host" else "" end
        - if .params.host then .params.host else "" end
        - if .params.profile then "--profile" else "" end
        - if .params.profile then .params.profile else "" end
      timeout: 15

---

# Brave Browser

Access browsing history, bookmarks, cookies, and session credentials from Brave Browser's local databases.

Brave is Chromium-based, so it uses the same cookie encryption scheme as Chrome:
AES-128-CBC with a key derived via PBKDF2 from a master password stored in macOS Keychain.

## Requirements

- **macOS only** — reads local SQLite databases
- **Brave Browser installed** — databases must exist at the standard paths
- **Full Disk Access** — System Settings > Privacy & Security > Full Disk Access (for the process reading the databases)
- **Brave closed (for cookies)** — SQLite WAL lock; or use `credential_get` which copies to `/tmp`

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

The `get_cookie_key` utility handles steps 1–2. The `credential_get` utility does the full pipeline.

## Cookie Extraction

Extract decrypted cookies for any domain. Used by other skills through cookie provider matchmaking.

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
webpage.list       Recently visited pages from Brave history
webpage.search     Search browsing history by URL or title

UTILITY            DESCRIPTION
--------------     -------------------------------------------------------
list_accounts      List Brave profiles with display names
get_cookie_key     Derive AES-128 key from Keychain (PBKDF2)
list_cookies       List raw (encrypted) cookies for a domain
cookie_get         Full pipeline: extract + decrypt any cookies for a domain
```
