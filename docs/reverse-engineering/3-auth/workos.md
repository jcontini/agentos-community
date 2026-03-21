# WorkOS Auth Pattern

WorkOS is a B2B auth platform used by many SaaS and desktop apps. It started
as an enterprise SSO product (SAML, SCIM) but added **WorkOS User Management**
in 2023 — a full-stack auth system covering consumer sign-up, social login,
*and* enterprise SSO in one package.

Part of [Layer 3: Auth & Runtime](./index.html). See also
[Electron deep dive](../6-desktop-apps/electron.md) for how WorkOS tokens
are stored in Electron apps.

---

## Recognizing WorkOS

The JWT `iss` (issuer) claim will contain `workos` or point to a custom auth
domain backed by WorkOS:

```json
{
  "iss": "https://auth.granola.ai/user_management/client_01JZJ0X...",
  "workos_id": "user_01K2JVZM...",
  "external_id": "c3b1fa46-...",
  "sid": "session_01KH4JGG...",
  "sign_in_method": "CrossAppAuth"
}
```

Key claims:

| Claim | Meaning |
|---|---|
| `workos_id` | WorkOS-native user ID (`user_01...`) |
| `external_id` | Previous auth provider's user UUID (preserved on migration) |
| `sid` | WorkOS session ID (`session_01...`) |
| `sign_in_method` | How the session was created: `SSO`, `Password`, `GoogleOAuth`, `CrossAppAuth` |
| `iss` | Contains `/user_management/client_<id>` for WorkOS User Management |

---

## Token File Shape

Apps that store WorkOS tokens locally typically use one of these shapes:

### Post-migration (Supabase → WorkOS)

```json
{
  "workos_tokens": "{\"access_token\":\"eyJ...\",\"refresh_token\":\"...\",\"expires_in\":21599,\"obtained_at\":1234567890,\"session_id\":\"session_01...\",\"external_id\":\"uuid\",\"sign_in_method\":\"CrossAppAuth\"}",
  "session_id": "session_01...",
  "user_info": "{\"id\":\"uuid\",\"email\":\"...\"}"
}
```

Note: `workos_tokens` is a **JSON string** (double-encoded), not an object.

```python
import json

with open("supabase.json") as f:
    raw = json.load(f)

tokens = json.loads(raw["workos_tokens"])   # parse the inner string
access_token  = tokens["access_token"]
refresh_token = tokens["refresh_token"]
expires_in    = tokens["expires_in"]        # seconds
obtained_at   = tokens["obtained_at"]       # ms epoch
```

### Native WorkOS storage

Some apps store tokens more directly:

```json
{
  "access_token": "eyJ...",
  "refresh_token": "...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

---

## Token Lifecycle

WorkOS access tokens are **short-lived** (typically 6 hours / `21600s`).

```python
import time, json, base64

def is_expired(token: str, buffer_s: int = 300) -> bool:
    payload = token.split('.')[1]
    payload += '=' * (4 - len(payload) % 4)
    claims = json.loads(base64.urlsafe_b64decode(payload))
    return claims['exp'] < time.time() + buffer_s

def get_token(token_file: str) -> str:
    with open(token_file) as f:
        raw = json.load(f)
    tokens = json.loads(raw.get("workos_tokens", "{}")) or raw
    access = tokens["access_token"]
    if is_expired(access):
        # Option A: open the app to refresh  
        # Option B: call the WorkOS refresh endpoint directly
        raise ValueError("Token expired — open the app to refresh")
    return access
```

### Refreshing without the app

If you have the `refresh_token` and `client_id`, you can refresh directly:

```python
import httpx, json

def refresh_workos_token(refresh_token: str, client_id: str, auth_domain: str) -> dict:
    """auth_domain e.g. 'https://auth.granola.ai'"""
    resp = httpx.post(f"{auth_domain}/user_management/authenticate", json={
        "client_id":     client_id,
        "grant_type":    "refresh_token",
        "refresh_token": refresh_token,
    })
    resp.raise_for_status()
    return resp.json()
```

The `client_id` is embedded in the `iss` claim:
`https://auth.example.com/user_management/client_01JZJ0X...` →
`client_01JZJ0X...`

---

## Calling the API

WorkOS-protected APIs expect a standard Bearer token plus usually some
app-specific identity headers. Always check the bundle for custom headers
before assuming a 401 is a token problem:

```python
import json, httpx
from pathlib import Path

TOKEN_FILE = Path.home() / "Library/Application Support/AppName/supabase.json"

def get_headers() -> dict:
    with open(TOKEN_FILE) as f:
        raw = json.load(f)
    tokens = json.loads(raw["workos_tokens"])
    return {
        "Authorization": f"Bearer {tokens['access_token']}",
        "X-Client-Version": "1.0.0",       # from app package.json
        "X-Client-Platform": "darwin",
        # Add X-Workspace-Id, X-Device-Id etc. if the app sends them
    }

with httpx.Client(http2=True) as client:
    resp = client.post("https://api.example.com/v1/some-endpoint",
        json={"param": "value"},
        headers=get_headers())
    print(resp.json())
```

---

## Supabase → WorkOS Migration

Many companies migrated from Supabase Auth to WorkOS. Signs you've hit a
migrated app:

1. Token file named `supabase.json` but contains `workos_tokens` key
2. JWT has both `workos_id` and `external_id` (the old Supabase UUID)
3. `iss` points to a custom domain (not `supabase.co`)
4. Database tables still use the old Supabase UUID as primary key

The migration preserves the old UUID as `external_id` precisely so FK
constraints don't need to be updated.

**Why migrate?** Supabase Auth is great for consumer apps; WorkOS adds
enterprise SSO (SAML/OIDC), SCIM directory sync, and an admin portal.
B2B SaaS companies migrate when enterprise customers demand SSO.

Common migration path:

```
Supabase Auth → WorkOS User Management → (optionally) full WorkOS SSO
```

Competitors in this space: **Clerk** (more consumer/Next.js focused),
**Auth0** (enterprise, heavyweight), **Stytch** (developer-first).
