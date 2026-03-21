# Auth Flows

When a skill needs credentials from a web dashboard (API keys, session tokens), the flow is: **discover with Playwright, implement with HTTPX**.

## The pattern

1. **Discover** — use the Playwright skill interactively to walk through the login/signup flow. `capture_network` reveals endpoints, `cookies` shows what session cookies get set, `inspect` shows form structure.
2. **Implement** — write the login flow as Python + `httpx` in the skill's `.py` file. Use `http2=True`, `follow_redirects=True`, and inject cookies from `params.auth.cookies` or `_call` to other skills (e.g. Gmail for magic links, `brave-browser` for Google session cookies).
3. **Store** — return extracted credentials via `__secrets__` so the engine stores them securely. The LLM never sees raw secret values.
4. **Test** — `test-skills.cjs` should work without a running browser. If your skill needs Playwright at runtime, rethink the approach.

## Dashboard connections

Skills with web dashboards declare a `dashboard` connection alongside their `api` connection:

```yaml
connections:
  api:
    base_url: "https://api.example.com"
    header: { x-api-key: .auth.key }

  dashboard:
    base_url: "https://dashboard.example.com"
    login:
      - sso: google
      - email_link: true
```

The `login` block declares available login methods. Login operations are Python functions that execute the flow with HTTPX. See `spec/sso-credential-bootstrap.md` in the engine repo for the full design.

## Secret-safe credential return

Login and API key extraction operations return credentials via `__secrets__`:

```python
def get_api_key(*, _call=None, **params):
    # ... HTTPX calls to get the key ...
    return {
        "__secrets__": [{
            "issuer": "api.example.com",
            "identifier": "user@example.com",
            "item_type": "api_key",
            "label": "Example API Key",
            "source": "example",
            "value": {"key": api_key},
            "metadata": {"masked": {"key": "••••" + api_key[-4:]}}
        }],
        "__result__": {"status": "authenticated", "identifier": "user@example.com"}
    }
```

The engine writes `__secrets__` to the credential store, creates an account entity on the graph, and strips the secrets before the MCP response reaches the agent.

## Key rules

- **Never import Playwright in skill Python code.** Playwright is a separate skill for investigation. Skill operations use `httpx`.
- **Never expose secrets in `__result__`.** Secrets go in `__secrets__` only. The agent sees masked versions via `metadata.masked`.
- **Use `_call` for cross-skill dispatch.** Need Gmail to check for a magic link? `_call("gmail.search_emails", {"query": "from:example.com subject:verify"})`. Need Google cookies? `_call("brave-browser.cookie_get", {"domain": ".google.com"})`.

For the full reverse engineering methodology, see [Auth & Runtime](../reverse-engineering/3-auth/README.md).
