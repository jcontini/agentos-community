---
id: firefox
name: Mozilla Firefox
description: "Browsing history, bookmarks, and cookies from Firefox, including cookie provider access for runtime cookie matchmaking"
color: "#FF7139"
website: "https://www.mozilla.org/firefox"

connections:
  places:
    sqlite:
      macos: ~/Library/Application Support/Firefox/Profiles/*/places.sqlite
  cookies_db:
    sqlite:
      macos: ~/Library/Application Support/Firefox/Profiles/*/cookies.sqlite

---

# Mozilla Firefox

Access browsing history, bookmarks, and cookies from Firefox's local databases.

## Data Sources

All data is read directly from Firefox's SQLite databases on disk. No network access needed.

- **History & Bookmarks** — `~/Library/Application Support/Firefox/Profiles/*/places.sqlite`
- **Cookies** — `~/Library/Application Support/Firefox/Profiles/*/cookies.sqlite`

Firefox profile directories have random prefixes (e.g., `abc123.default-release`). The SQL executor resolves glob patterns automatically and queries all matching profiles.

## Usage

### list_webpages / search_webpages

Browse and search Firefox history.

### list_bookmarks

List all bookmarks with URLs and dates.

### list_cookies

List cookies for a domain. **Firefox cookies are plaintext** — no decryption needed, unlike Chromium-based browsers.

### cookie_get

Provider-facing cookie extraction for connections that use cookie-based auth. When multiple providers match, the runtime asks the agent to get a choice from the user and retry with `cookie_provider` set to the selected provider id.
