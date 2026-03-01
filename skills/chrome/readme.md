---
id: chrome
name: Google Chrome
description: Browsing history, bookmarks, and cookies from Google Chrome
icon: icon.svg
color: "#4285F4"

website: https://www.google.com/chrome
platforms: [macos]

auth: none

connects_to: google-chrome

seed:
  - id: google-chrome
    types: [software]
    name: Google Chrome
    data:
      software_type: browser
      url: https://www.google.com/chrome
      platforms: [macos, windows, linux]
      wikidata_id: Q777
    relationships:
      - role: offered_by
        to: google

  - id: google
    types: [organization]
    name: Google
    data:
      type: company
      url: https://google.com
      wikidata_id: Q95

database:
  macos: "~/Library/Application Support/Google/Chrome/Default/History"

instructions: |
  Google Chrome browser — local data access via SQLite databases.
  - History: browsing history with visit counts and timestamps
  - Bookmarks: uses Chrome's JSON Bookmarks file via command executor
  - Cookie key derivation: derives the AES key from macOS Keychain for Chromium cookie decryption
  - All data is local, read-only, no network requests
  - Chrome timestamps are WebKit epoch (microseconds since 1601-01-01)
  - To convert to Unix: (chrome_time / 1000000) - 11644473600

testing:
  exempt:
    has_tests: "Local SQLite database — requires Chrome to be installed"

# ═══════════════════════════════════════════════════════════════════════════════
# TRANSFORMERS
# ═══════════════════════════════════════════════════════════════════════════════

transformers:
  webpage:
    terminology: Page
    mapping:
      id: .url
      url: .url
      title: .title
      data: '{ visit_count: .visit_count }'

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  webpage.list:
    description: List recently visited pages from Chrome browsing history
    returns: webpage[]
    params:
      limit:
        type: integer
        description: Maximum number of results
    sql:
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
    description: Search Chrome browsing history by URL or title
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

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

utilities:
  get_cookie_key:
    description: >
      Derive the AES-128 decryption key for Chrome cookies on macOS.
      Reads the password from macOS Keychain ("Chrome Safe Storage"),
      then runs PBKDF2-HMAC-SHA1 with salt "saltysalt" and 1003 iterations.
      Returns the hex-encoded 16-byte key.
    returns:
      key: string
    steps:
      steps:
        - id: get_password
          keychain:
            service: "Chrome Safe Storage"
            account: "Chrome"

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
      List cookies for a domain from Chrome's cookie database.
      Returns raw cookie data including hex-encoded encrypted values.
      Use get_cookie_key to get the decryption key, then decrypt individual
      values with the crypto executor (aes-128-cbc, IV = 20202020...x16).
      Chrome encrypted_value starts with "hex:763130" (v10 prefix) — strip
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
        description: Domain to get cookies for (e.g., "google.com")
      limit:
        type: integer
        description: Maximum number of cookies
    sql:
      database: '"~/Library/Application Support/Google/Chrome/Default/Cookies"'
      query: >
        SELECT name, host_key, path, encrypted_value,
               is_secure, is_httponly, expires_utc
        FROM cookies
        WHERE host_key LIKE :domain
        ORDER BY name
        LIMIT :limit
      params:
        domain: '"%" + .params.domain + "%"'
        limit: '.params.limit // 1000'

  list_logins:
    description: >
      List saved login entries from Chrome (usernames only, not passwords).
      Passwords are encrypted with the same key as cookies.
    returns:
      origin_url: string
      username_value: string
      date_created: integer
    params:
      domain:
        type: string
        description: Filter by domain (optional)
      limit:
        type: integer
    sql:
      database: '"~/Library/Application Support/Google/Chrome/Default/Login Data"'
      query: >
        SELECT origin_url, username_value,
               CAST((date_created / 1000000) - 11644473600 AS INTEGER) AS date_created_unix
        FROM logins
        WHERE username_value != ''
          AND (:domain IS NULL OR origin_url LIKE :domain)
        ORDER BY date_created DESC
        LIMIT :limit
      params:
        domain: 'if .params.domain then "%" + .params.domain + "%" else null end'
        limit: '.params.limit // 1000'
---

# Google Chrome

Access browsing history, bookmarks, cookies, and saved logins from Google Chrome's local databases.

## Data Sources

All data is read directly from Chrome's SQLite databases on disk. No network access, no Chrome extension needed.

- **History** — `~/Library/Application Support/Google/Chrome/Default/History`
- **Cookies** — `~/Library/Application Support/Google/Chrome/Default/Cookies`
- **Login Data** — `~/Library/Application Support/Google/Chrome/Default/Login Data`

## Operations

### webpage.list / webpage.search

Browse and search Chrome history. Returns web pages with visit counts.

### get_cookie_key

Derives the AES-128 decryption key for Chrome's encrypted cookies using the macOS Keychain and PBKDF2. This is the first step in the Chromium cookie decryption pipeline.

### list_cookies

Lists cookies for a domain. Values are encrypted — use `get_cookie_key` + AES-128-CBC decryption to read them.

## Cookie Decryption

Chrome encrypts cookie values on macOS using:
1. A master password stored in macOS Keychain under "Chrome Safe Storage"
2. PBKDF2-HMAC-SHA1 (salt: "saltysalt", 1003 iterations, 16-byte key)
3. AES-128-CBC (IV: all spaces = `20` repeated 16 times)

The `get_cookie_key` utility handles steps 1-2 automatically.
