---
id: brave-browser
name: Brave Browser
description: Browsing history, bookmarks, and cookies from Brave Browser on macOS — including session key extraction for claude.ai
icon: icon.svg
color: "#F83B1D"

website: https://brave.com
platforms: [macos]

auth: none

connects_to: brave-browser-app

# Brave (Chromium-based) stores cookies encrypted in SQLite.
# The encryption key lives in macOS Keychain under "Brave Safe Storage" / "Brave".
# This skill exposes a credential_get utility that extracts and decrypts
# the sessionKey cookie for claude.ai, usable by consumer skills via provides:.
provides:
  - service: claude-ai
    scopes: [sessionKey]
    via: credential_get
    account_param: account
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

instructions: |
  Brave Browser — local data access via SQLite databases (Chromium-based).
  - Cookies: encrypted with AES-128-CBC, key derived via PBKDF2 from macOS Keychain
  - History: browsing history with visit counts and WebKit timestamps
  - Cookie key derivation: "Brave Safe Storage" service, "Brave" account in Keychain
  - Keychain account is "Brave" (not "Chromium") — verified on macOS
  - Chrome timestamps are WebKit epoch (microseconds since 1601-01-01)
  - To convert to Unix: (chrome_time / 1000000) - 11644473600
  - Brave must NOT be running when reading the Cookies DB (file lock),
    OR use the credential_get utility which copies to /tmp first.
  - The claude.ai sessionKey cookie lives on host .platform.claude.com

testing:
  exempt:
    has_tests: "Local SQLite database — requires Brave Browser to be installed"

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
            password: "{{get_password.value}}"
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

  credential_get:
    description: |
      Extract and decrypt the sessionKey (or any named cookie) from Brave Browser
      for a given host. Used by consumer skills via provides: to get claude.ai session credentials.

      Copies the Cookies DB to /tmp to avoid file-lock issues when Brave is running,
      derives the AES key from macOS Keychain, and decrypts the v10 cookie value.

      Returns { session_key: "sk-ant-..." }.
    params:
      host:
        type: string
        description: "Host pattern to match (default: platform.claude.com)"
      name:
        type: string
        description: "Cookie name (default: sessionKey)"
      account:
        type: string
        description: "Brave profile name (optional, default profile used if omitted)"
    returns:
      session_key: string
    steps:
      steps:
        - id: cookie
          command:
            binary: bash
            args:
              - "-l"
              - "-c"
              - "python3 ~/dev/agentos-community/skills/brave-browser/get-cookie.py --host '{{params.host | default:platform.claude.com}}' --name '{{params.name | default:sessionKey}}'"

      response:
        transform: |
          { session_key: .cookie.value }

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

## Claude.ai Session Key

The `sessionKey` cookie for claude.ai lives on host `.platform.claude.com`.

```
use({ skill: "brave-browser", tool: "credential_get", params: {} })
// → { session_key: "sk-ant-..." }
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
credential_get     Full pipeline: extract + decrypt sessionKey for claude.ai
```
