# Electron App Deep Dive

Electron apps are Chromium + Node.js packaged into a desktop shell. The JS
bundle is readable, the storage is standard Chromium formats, and the auth
tokens are often sitting in a JSON file. Once you know where to look, Electron
is one of the easiest desktop targets.

Part of [Layer 6: Desktop Apps](./index.html). See also [3-auth](../3-auth/index.html) for
general auth patterns.

---

## Identify Electron

```bash
ls /Applications/SomeApp.app/Contents/Resources/
# Look for: app.asar  ← bundled JS/HTML/CSS
#           app/      ← unpacked (less common)

file /Applications/SomeApp.app/Contents/MacOS/SomeApp
# Should reference Electron framework
```

---

## Extract and Read the Bundle

```bash
# One-shot: extract app.asar to /tmp/app
npx @electron/asar extract /Applications/SomeApp.app/Contents/Resources/app.asar /tmp/app

ls /tmp/app
# Typical: dist-electron/  dist-app/  node_modules/  package.json
```

The bundle is minified but readable. Variable names are mangled; string
literals (URLs, endpoint paths, header names) are **not** minified. Use these
to navigate.

### Find all API endpoints

```bash
grep -o "[a-zA-Z]*\.example\.com[^\"']*" /tmp/app/dist-electron/main/index.js | sort -u
```

### Find all subdomains

```bash
grep -o "[a-z-]*\.example\.com" /tmp/app/dist-electron/main/index.js | sort -u
```

### Find auth header construction

```bash
# Look for Authorization, X-Client-*, bearer
grep -o ".{0,150}Authorization.{0,150}" /tmp/app/dist-electron/main/index.js | head -10
```

---

## Storage Locations

All Electron app data lives in:

```
~/Library/Application Support/<AppName>/
```

| File / Dir | What it contains |
|---|---|
| `*.json` files | Auth tokens, config, feature flags |
| `Cookies` | SQLite — Chromium encrypted cookies (usually empty in Electron) |
| `Local Storage/leveldb/` | LevelDB — localStorage, sometimes tokens |
| `IndexedDB/file__0.indexeddb.leveldb/` | IndexedDB — app state, can contain tokens |
| `Preferences` | JSON — per-profile settings |

Electron apps typically store auth in **JSON files**, not browser cookies,
because the main process (Node.js) writes them directly without going through
Chromium's cookie jar.

---

## Find the Token

### 1. Scan JSON files for tokens

```bash
for f in ~/Library/Application\ Support/AppName/*.json; do
  echo "=== $f ===" && python3 -c "
import json, sys
with open('$f') as f: d = json.load(f)
def walk(obj, p=''):
    if isinstance(obj, dict):
        for k,v in obj.items(): walk(v, p+'.'+k)
    elif isinstance(obj, str) and len(obj) > 20:
        print(f'  {p}: {obj[:60]}')
walk(d)
"
done
```

### 2. Look for JWT patterns

```bash
# JWTs start with eyJ (base64url of {"alg":...)
grep -r "eyJ" ~/Library/Application\ Support/AppName/ --include="*.json" -l
```

### 3. Decode any JWT you find

```python
import base64, json

def decode_jwt(token):
    parts = token.split('.')
    def b64d(s):
        s += '=' * (4 - len(s) % 4)
        return json.loads(base64.urlsafe_b64decode(s))
    return b64d(parts[0]), b64d(parts[1])   # header, payload

header, payload = decode_jwt(token)
print("iss:", payload.get("iss"))   # who issued it
print("exp:", payload.get("exp"))   # expiry
print("claims:", list(payload.keys()))
```

The `iss` field tells you the auth provider (WorkOS, Supabase, Auth0, Okta,
etc.) and which client ID / tenant.

---

## Required Headers

Most Electron APIs reject requests missing client identification headers. Find
them by searching the bundle for the header-building function:

```bash
# Common patterns: X-Client-*, X-App-*, platform, device-id
grep -o ".{0,100}X-Client.{0,200}" /tmp/app/dist-app/assets/operationBuilder.js | head -5
```

Typical Electron API headers:

| Header | Example | Notes |
|---|---|---|
| `X-Client-Version` | `7.71.1` | App version from `package.json` |
| `X-Client-Platform` / `X-Granola-Platform` | `darwin` | OS platform |
| `X-Workspace-Id` | UUID | Multi-tenant identifier |
| `X-Device-Id` | UUID | Persisted device fingerprint |

Without these, the server may return `{"message":"Unsupported client"}` even
with a valid token.

Get the version:

```bash
cat /tmp/app/package.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['version'])"
```

---

## Auth Migration Pattern (Supabase → WorkOS)

Many Electron apps launched with **Supabase Auth** and later migrated to
**WorkOS** (or Clerk, Auth0, etc.) for enterprise SSO. The telltale sign:

```
~/Library/Application Support/AppName/supabase.json   ← filename from v1
  → contents: { "workos_tokens": "...", "user_info": ... }  ← migration artifact
```

The filename is kept for backward compatibility, but the contents changed.
The old Supabase user UUID is preserved as `external_id` in the new JWT so
database foreign keys don't break.

**How to detect a migration:**

```python
import json

with open("supabase.json") as f:
    d = json.load(f)

if "workos_tokens" in d:
    print("Migrated to WorkOS — parse workos_tokens as JSON for the JWT")
elif "access_token" in d:
    print("Still on Supabase — access_token is the JWT directly")
elif "session" in d:
    print("Supabase session object — check session.access_token")
```

See [workos.md](../3-auth/workos.md) for the full WorkOS token model.

---

## CrossAppAuth — Desktop ↔ Web Session Handoff

Some Electron apps share a session between the desktop client and the web app
without requiring a separate login. The pattern:

1. User logs in on the **web app** (browser)
2. Desktop app detects the session (via deep link, polling, or IPC)
3. Desktop calls an `auth-handoff-complete`-style endpoint with the web session
4. Server mints a new desktop token (different expiry, different claims)

You'll see this as `sign_in_method: "CrossAppAuth"` in the JWT payload, or
as an endpoint like `/v1/auth-handoff-complete` in the app bundle.

To find:

```bash
grep -o "[^\"]*auth.handoff[^\"]*\|[^\"]*cross.app[^\"]*" /tmp/app/dist-electron/main/index.js
```

---

## Feature Flags

Electron apps frequently gate features behind server-controlled flags stored
in `local-state.json` or a similar config file:

```python
import json

with open("local-state.json") as f:
    d = json.load(f)

flags = d.get("featureFlags", {})
for k, v in flags.items():
    print(f"  {k}: {v}")
```

If an API endpoint returns `403 Forbidden` or `{"enabled": false}` even with
a valid token, check whether there's a feature flag that needs to be `true`.
Some flags are user-controlled (toggle in Settings), others are server-pushed
and require a plan upgrade.

---

## Chromium Storage (usually empty)

Electron apps *can* use Chromium cookies and localStorage, but most don't —
the Node.js main process writes tokens directly to JSON files instead.

If you do find a populated `Cookies` database, decrypt it the same way as
Brave or Chrome:

```bash
# Check if there's a Keychain entry
security find-generic-password -s "AppName Safe Storage" -a "AppName" -w

# Cookies database
sqlite3 ~/Library/Application\ Support/AppName/Cookies \
  "SELECT name, host_key FROM cookies LIMIT 20;"
```

See the `skills/brave-browser/` skill for the full
Chromium cookie decryption pipeline (PBKDF2 + AES-128-CBC).

---

## Checklist

```
□ Find app.asar and extract it
□ Grep for all subdomains and API endpoints
□ Find the header-building function → identify required custom headers
□ Scan ~/Library/Application Support/<App>/*.json for tokens
□ Decode any JWT → check iss, exp, claims
□ Detect auth migration (supabase.json but workos_tokens key?)
□ Test token against a known-working endpoint with correct headers
□ Check for feature flags gating the feature you need
```
