# Amazon

Access your Amazon account using browser session cookies. No API keys, no OAuth — log into Amazon in a browser whose cookies are visible to an installed cookie provider integration; this skill uses those cookies on requests.

## How It Works

Amazon uses **pure cookie-based session auth**. When you log into Amazon in your browser, it stores session cookies that persist for weeks or months. The runtime resolves a cookie provider for `.amazon.com` and injects those cookies on requests.

### Authentication Flow

1. You log into Amazon in a browser covered by a cookie provider integration
2. The engine obtains `.amazon.com` cookies from that provider
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
