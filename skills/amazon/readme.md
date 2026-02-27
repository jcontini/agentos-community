---
id: amazon
name: Amazon
description: Access your Amazon account using browser session cookies
icon: icon.svg
color: "#FF9900"

website: https://www.amazon.com
platforms: [macos]

auth:
  cookies:
    domain: ".amazon.com"
    names: ["x-main", "session-id", "session-token", "ubid-main", "at-main", "sess-at-main", "i18n-prefs"]
    browser: firefox

connects_to: amazon

seed:
  - id: amazon
    types: [organization]
    name: Amazon
    data:
      type: company
      url: https://amazon.com
      founded: "1994"
      wikidata_id: Q3884

instructions: |
  Amazon consumer account access via browser session cookies.
  
  Authentication is fully automatic:
  - Cookies are extracted from Firefox (or Chrome) browser databases
  - The user must be logged into Amazon in their browser
  - Session cookies (x-main, session-id, session-token) persist for weeks/months
  - No API key, no OAuth, no password storage
  
  If requests fail with redirects to the login page, the session has expired.
  Tell the user: "Your Amazon session has expired. Please log into Amazon in Firefox."
  
  Amazon does not provide a consumer JSON API. Responses are HTML pages.
  The check_session utility verifies auth is working by checking for the
  presence of the user's name in the account page response.

testing:
  exempt:
    has_tests: "Requires active Amazon browser session — cannot test without credentials"

# ==============================================================================
# UTILITIES
# ==============================================================================

utilities:
  check_session:
    description: >
      Verify that Amazon browser cookies are valid by fetching the account page.
      Returns the page title — if authenticated, it contains "Your Account".
      If cookies are expired, Amazon redirects to the login page.
    returns:
      authenticated: boolean
      title: string
      status_code: integer
    rest:
      method: GET
      url: "https://www.amazon.com/gp/css/homepage.html"
      headers:
        User-Agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        Accept: "text/html,application/xhtml+xml"
        Accept-Language: "en-US,en;q=0.9"
      response:
        root: "/"
---

# Amazon

Access your Amazon account using browser session cookies. No API keys, no OAuth — just log into Amazon in Firefox and this skill handles the rest.

## How It Works

Amazon uses **pure cookie-based session auth**. When you log into Amazon in your browser, it stores session cookies that persist for weeks or months. This skill extracts those cookies and uses them to make authenticated requests on your behalf.

### Authentication Flow

1. You log into Amazon in Firefox (you probably already are)
2. AgentOS reads cookies from Firefox's local database (plaintext, no decryption needed)
3. Cookies are injected as a `Cookie` header on every request
4. Sessions last weeks/months — no refresh needed

### Key Cookies

| Cookie | Purpose |
|--------|---------|
| `x-main` | Primary session identifier (survives password changes) |
| `session-id` | Session identifier |
| `session-token` | CSRF-like token for requests |
| `at-main` | Access token |
| `ubid-main` | Browser identifier |

## Utilities

### check_session

Verifies that your Amazon session is active by fetching your account page. If authenticated, the response contains "Your Account" in the title.

## Limitations

- Amazon does not provide a consumer JSON API — all responses are HTML
- Sessions eventually expire (rare, usually weeks/months)
- When expired, log into Amazon in Firefox again
