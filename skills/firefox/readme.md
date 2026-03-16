---
id: firefox
name: Mozilla Firefox
description: Browsing history, bookmarks, and cookies from Firefox, including cookie provider access for auth consumers
icon: icon.svg
color: "#FF7139"

website: https://www.mozilla.org/firefox
auth: none

# Firefox cookies are stored plaintext in SQLite, so this skill can act as a
# lightweight cookie provider for consumer skills that declare auth.cookies.
provides:
  - service: cookies
    description: "Extract plaintext Firefox cookies from local profiles for auth consumers."
    via: cookie_get
    account_param: domain

database:
  macos: "~/Library/Application Support/Firefox/Profiles/*/places.sqlite"
# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
  webpage:
    id: .url
    name: '.title // .url'
    url: .url
    data.visit_count: .visit_count
    data.last_visit_unix: .last_visit_unix

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  list_webpages:
    description: List recently visited pages from Firefox browsing history
    returns: webpage[]
    params:
      limit:
        type: integer
        description: Maximum number of results
    sql:
      query: >
        SELECT p.url, p.title, p.visit_count,
               CAST(p.last_visit_date / 1000000 AS INTEGER) AS last_visit_unix
        FROM moz_places p
        WHERE p.hidden = 0
          AND p.visit_count > 0
          AND p.url NOT LIKE 'place:%'
        ORDER BY p.last_visit_date DESC
        LIMIT :limit
      params:
        limit: '.params.limit // 1000'
      response:
        root: "/"

  search_webpages:
    description: Search Firefox browsing history by URL or title
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
        SELECT p.url, p.title, p.visit_count,
               CAST(p.last_visit_date / 1000000 AS INTEGER) AS last_visit_unix
        FROM moz_places p
        WHERE p.hidden = 0
          AND p.visit_count > 0
          AND p.url NOT LIKE 'place:%'
          AND (p.url LIKE :query OR p.title LIKE :query)
        ORDER BY p.last_visit_date DESC
        LIMIT :limit
      params:
        query: '"%" + .params.query + "%"'
        limit: '.params.limit // 1000'
      response:
        root: "/"

# ═══════════════════════════════════════════════════════════════════════════════
# ADDITIONAL OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

  list_bookmarks:
    description: List Firefox bookmarks (excluding folders and separators)
    returns:
      title: string
      url: string
      date_added: integer
    params:
      folder:
        type: string
        description: Filter by parent folder title (optional)
      limit:
        type: integer
        description: Maximum number of results
    sql:
      database: '"~/Library/Application Support/Firefox/Profiles/*/places.sqlite"'
      query: >
        SELECT b.title AS bookmark_title, p.url, p.title,
               CAST(b.dateAdded / 1000000 AS INTEGER) AS date_added_unix
        FROM moz_bookmarks b
        JOIN moz_places p ON b.fk = p.id
        WHERE b.type = 1
          AND p.url NOT LIKE 'place:%'
        ORDER BY b.dateAdded DESC
        LIMIT :limit
      params:
        limit: '.params.limit // 1000'

  list_cookies:
    description: >
      List cookies for a domain from Firefox. Firefox cookies are stored in
      plaintext — no decryption needed (unlike Chromium browsers).
    returns:
      name: string
      value: string
      host: string
      path: string
      expiry: integer
      is_secure: integer
      is_httponly: integer
    params:
      domain:
        type: string
        required: true
        description: Domain to get cookies for (e.g., "google.com")
      limit:
        type: integer
        description: Maximum number of cookies
    sql:
      database: '"~/Library/Application Support/Firefox/Profiles/*/cookies.sqlite"'
      query: >
        SELECT name, value, host, path, expiry,
               isSecure AS is_secure, isHttpOnly AS is_httponly
        FROM moz_cookies
        WHERE host LIKE :domain
        ORDER BY name
        LIMIT :limit
      params:
        domain: '"%" + .params.domain + "%"'
        limit: '.params.limit // 1000'

  cookie_get:
    description: |
      Extract cookies for a domain from Firefox's local cookie database.
      This is the provider interface for cookie matchmaking with consumer skills.
      If multiple installed browser skills provide cookies, the agent should ask
      the user which provider to use and retry with `cookie_provider`.
    params:
      domain:
        type: string
        required: true
        description: "Cookie domain to match (e.g., '.claude.ai', '.amazon.com')"
      names:
        type: string
        description: "Comma-separated cookie names to filter (e.g., 'sessionKey,csrf_token')"
      limit:
        type: integer
        description: Maximum number of cookies
    returns:
      domain: string
      cookies: array
      count: integer
      source: string
    steps:
      steps:
        - id: get_cookies
          sql:
            database: '"~/Library/Application Support/Firefox/Profiles/*/cookies.sqlite"'
            query: >
              SELECT name, value, host, path, expiry,
                     isSecure AS is_secure, isHttpOnly AS is_httponly
              FROM moz_cookies
              WHERE host LIKE :domain
                AND (:names = '' OR instr(',' || :names || ',', ',' || name || ',') > 0)
              ORDER BY name
              LIMIT :limit
            params:
              domain: '"%" + .params.domain + "%"'
              names: '.params.names // ""'
              limit: '.params.limit // 1000'
      response:
        mapping:
          domain: '.params.domain'
          cookies: '.get_cookies'
          count: '.get_cookies | length'
          source: '"firefox"'
---

# Mozilla Firefox

Access browsing history, bookmarks, and cookies from Firefox's local databases.

## Data Sources

All data is read directly from Firefox's SQLite databases on disk. No network access needed.

- **History & Bookmarks** — `~/Library/Application Support/Firefox/Profiles/*/places.sqlite`
- **Cookies** — `~/Library/Application Support/Firefox/Profiles/*/cookies.sqlite`

Firefox profile directories have random prefixes (e.g., `abc123.default-release`). The SQL executor resolves glob patterns automatically and queries all matching profiles.

## Operations

### list_webpages / search_webpages

Browse and search Firefox history.

### list_bookmarks

List all bookmarks with URLs and dates.

### list_cookies

List cookies for a domain. **Firefox cookies are plaintext** — no decryption needed, unlike Chromium-based browsers.

### cookie_get

Provider-facing cookie extraction for auth consumers. When multiple installed skills provide cookies, the runtime asks the agent to get a choice from the user and retry with `cookie_provider` set to the selected skill id.
