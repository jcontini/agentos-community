---
id: firefox
name: Mozilla Firefox
description: Browsing history, bookmarks, and cookies from Firefox
icon: icon.svg
color: "#FF7139"

website: https://www.mozilla.org/firefox
platforms: [macos]

auth: none

connects_to: firefox

seed:
  - id: firefox
    types: [software]
    name: Mozilla Firefox
    data:
      software_type: browser
      url: https://www.mozilla.org/firefox
      platforms: [macos, windows, linux]
      wikidata_id: Q698
    relationships:
      - role: offered_by
        to: mozilla

  - id: mozilla
    types: [organization]
    name: Mozilla Foundation
    data:
      type: nonprofit
      url: https://mozilla.org
      founded: "2003"
      wikidata_id: Q9661

database:
  macos: "~/Library/Application Support/Firefox/Profiles/*/places.sqlite"

instructions: |
  Mozilla Firefox browser — local data access via SQLite databases.
  - History and bookmarks are in places.sqlite
  - Cookies are in cookies.sqlite (plaintext — no decryption needed!)
  - Firefox uses glob paths (profiles have random prefixes like "abc123.default")
  - The SQL executor resolves globs automatically, querying all matching profiles
  - Timestamps: Firefox uses microseconds since Unix epoch (PRTime)
  - To convert to seconds: time / 1000000
  - Bookmark types: 1 = bookmark, 2 = folder, 3 = separator

testing:
  exempt:
    has_tests: "Local SQLite database — requires Firefox to be installed"

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

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  webpage.list:
    description: List recently visited pages from Firefox browsing history
    returns: webpage[]
    params:
      limit:
        type: integer
        default: 50
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
        limit: '.params.limit // 50'
      response:
        root: "/"

  webpage.search:
    description: Search Firefox browsing history by URL or title
    returns: webpage[]
    params:
      query:
        type: string
        required: true
        description: Search term (matches URL and title)
      limit:
        type: integer
        default: 25
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
        limit: '.params.limit // 25'
      response:
        root: "/"

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

utilities:
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
        default: 100
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
        limit: '.params.limit // 100'

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
        default: 100
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
        limit: '.params.limit // 100'
---

# Mozilla Firefox

Access browsing history, bookmarks, and cookies from Firefox's local databases.

## Data Sources

All data is read directly from Firefox's SQLite databases on disk. No network access needed.

- **History & Bookmarks** — `~/Library/Application Support/Firefox/Profiles/*/places.sqlite`
- **Cookies** — `~/Library/Application Support/Firefox/Profiles/*/cookies.sqlite`

Firefox profile directories have random prefixes (e.g., `abc123.default-release`). The SQL executor resolves glob patterns automatically and queries all matching profiles.

## Operations

### webpage.list / webpage.search

Browse and search Firefox history.

### list_bookmarks

List all bookmarks with URLs and dates.

### list_cookies

List cookies for a domain. **Firefox cookies are plaintext** — no decryption needed, unlike Chromium-based browsers.
