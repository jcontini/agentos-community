---
id: amazon
name: Amazon
description: Access your Amazon account using browser session cookies
icon: icon.svg
color: "#FF9900"

website: https://www.amazon.com
connections:
  web:
    base_url: "https://www.amazon.com"
    cookies:
      domain: ".amazon.com"
      names: ["x-main", "session-id", "session-token", "ubid-main", "at-main", "sess-at-main", "i18n-prefs"]

# ==============================================================================
# OPERATIONS
# ==============================================================================

operations:
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
      url: /gp/css/homepage.html
      headers:
        User-Agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        Accept: "text/html,application/xhtml+xml"
        Accept-Language: "en-US,en;q=0.9"
      response:
        root: "/"
---

# Amazon

Access your Amazon account using browser session cookies. No API keys, no OAuth — just log into Amazon in a browser backed by an installed cookie provider skill and this skill handles the rest.

## How It Works

Amazon uses **pure cookie-based session auth**. When you log into Amazon in your browser, it stores session cookies that persist for weeks or months. This skill asks an installed cookie provider skill for those cookies and uses them to make authenticated requests on your behalf.

### Authentication Flow

1. You log into Amazon in a browser with an installed cookie provider skill
2. AgentOS asks that provider skill for `.amazon.com` cookies
3. Cookies are injected as a `Cookie` header on every request
4. Sessions last weeks/months — no refresh needed
5. If multiple cookie providers are installed, the agent should ask the user which browser/provider to use

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
- When expired, log into Amazon again in the browser/provider you want to use
