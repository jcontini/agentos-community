---
id: reverse-engineer
name: Reverse Engineer
description: Guide for reverse engineering desktop app authentication and credential storage on macOS
icon: icon.svg
color: "#6366F1"

website: https://github.com/jcontini/agentos-community

auth: none

testing:
  exempt:
    seed: "Meta-skill — no external service, documents local macOS investigation techniques"

instructions: |
  Guide for reverse engineering how desktop apps store credentials on macOS.
  Use this to figure out if and how AgentOS can authenticate with a given app
  without requiring the user to generate separate API keys.

  The goal: can we read the app's auth token and call its API ourselves?
---

# Reverse Engineer

A guide for investigating how desktop apps store credentials on macOS, based on
real reverse engineering of Claude Desktop, ChatGPT Desktop, and other apps.

---

## Decision Tree: What Kind of App Is It?

Before doing anything, determine the app type. Everything flows from this.

```
Is it in the App Store?
├── Yes → Sandboxed → tokens in ~/Library/Containers/{bundle-id}/ → harder
└── No  → Not sandboxed → tokens in ~/Library/Application Support/{bundle-id}/

What framework?
├── Electron → SafeStorage (Keychain) → READABLE ✅
├── Native Swift/SwiftUI → Keychain Group (team-signed) → BLOCKED ❌
├── Native Cocoa/ObjC → Varies (Keychain or plist) → INVESTIGATE
└── Web wrapper (WKWebView) → WebKit cookie storage → INVESTIGATE
```

---

## App Type Detection

### 1. Check the Frameworks directory

```bash
ls /Applications/AppName.app/Contents/Frameworks/ | head -20
```

| Framework seen | App type |
|---------------|----------|
| `Electron Framework.framework` | Electron |
| `node_modules/` in Resources | Electron |
| `SwiftUI.framework`, `Combine.framework` | Native Swift |
| `Lottie.framework`, `Sentry.framework` | Native (could be any) |
| `WebKit.framework` | Uses embedded browser |

### 2. Check for Keychain entries

```bash
# For Electron apps — look for SafeStorage entry:
security find-generic-password -s "{AppName} Safe Storage" -w

# For native apps — try bundle ID:
security find-generic-password -s "com.company.appname" -w

# For internet passwords:
security find-internet-password -s "domain.com" -w
```

**IMPORTANT:** Never use `security dump-keychain` — it scans ALL entries and
triggers a security prompt for every app in the keychain.

### 3. Read the app binary for clues

```bash
# Look for auth-related strings (non-prompting, safe):
strings /Applications/AppName.app/Contents/MacOS/AppName | grep -i \
  "keychain\|token\|auth\|bearer\|safe.storage\|kSecAttr" | head -40

# For framework-based apps:
strings /Applications/AppName.app/Contents/Frameworks/AppName.framework/AppName \
  | grep -i "keychain\|token\|auth\|api\." | head -40
```

Useful things to look for:
- `{Name} Safe Storage` → Electron, SafeStorage key name
- `com.company.app://auth0...` → OAuth via Auth0, native app
- `kSecAttrService` values → exact Keychain service name
- API endpoint URLs → what to call once authenticated
- Auth header names (`Authorization`, `Authorization-Id-Token`, `x-api-key`, etc.)

---

## Approach by App Type

### Electron Apps (SafeStorage) ✅ READABLE

**Examples:** Claude Desktop, Slack, Discord, VS Code, Cursor

**How it works:**
1. App stores an encryption key in Keychain under `{AppName} Safe Storage`
2. Uses that key to encrypt config with AES-128-CBC + PBKDF2
3. Stores encrypted blob as base64 in a JSON config file
4. AgentOS's `safestorage` auth type handles this automatically

**Steps:**
```bash
# 1. Find the config file (usually contains encrypted token)
ls "~/Library/Application Support/{AppName}/"

# 2. Find the JSON config with the encrypted blob
cat "~/Library/Application Support/{AppName}/config.json"

# 3. Verify SafeStorage key exists in Keychain
security find-generic-password -s "{AppName} Safe Storage" -w

# 4. Read the JSON to find which key holds the token
# Look for base64 values starting with "v10" or "v11" when decoded
```

**Skill auth config:**
```yaml
auth:
  type: safestorage
  app: "AppName"                              # Keychain service = "{app} Safe Storage"
  config: "~/Library/Application Support/AppName/config.json"
  key: "oauth:tokenCache"                    # JSON key holding the encrypted blob
  token_field: "token"                       # Field inside the decrypted JSON
  refresh_field: "refreshToken"              # Optional refresh token field
  expires_field: "expiresAt"                 # Optional expiry field
  refresh_url: "https://api.example.com/token"
```

---

### Native macOS Apps (Keychain Groups) ❌ BLOCKED

**Examples:** ChatGPT Desktop

**How it works:**
- Token stored in Apple Keychain Sharing Group tied to Apple Developer Team ID
- Format: `{TEAM_ID}.group.{bundle-id}` (e.g. `2DC432GLL2.group.com.openai.chat`)
- Only apps signed with the same Team ID can access these entries
- `security` CLI cannot read them — requires being in the same signing group

**Detection:**
```bash
# Find team-id Keychain groups in binary
strings /Applications/AppName.app/Contents/Frameworks/AppName.framework/AppName \
  | grep -E "[A-Z0-9]{10}\.group\."
```

If you see `XXXXXXXXXX.group.com.company.app` → this is a Keychain Group → blocked.

**Alternatives:**
- Use the official API with a user-provided API key instead
- Check if the app has a web login in Firefox/Chrome → browser cookies

---

### WebKit / WKWebView Apps (Cookie Storage) 🔶 SOMETIMES READABLE

**Examples:** Some native apps embed WKWebView for their UI

**Storage location:**
```bash
ls ~/Library/WebKit/{bundle-id}/WebsiteData/
```

**Check LocalStorage (UTF-16 encoded):**
```bash
sqlite3 ~/Library/WebKit/{bundle-id}/WebsiteData/Default/{hash}/LocalStorage/localstorage.sqlite3 \
  "SELECT key, hex(value) FROM ItemTable"
```

**Check HTTP cookies:**
```bash
sqlite3 ~/Library/HTTPStorages/{bundle-id}/httpstorages.sqlite ".tables"
```

**Limitations:**
- WebKit cookies are encrypted using a per-app salt (`WebsiteData/Default/salt`)
- The salt file + a device key derivation is needed to decrypt
- Not currently supported by AgentOS resolvers

---

### Firefox Browser Cookies ✅ READABLE (no Keychain)

**For any service the user is logged into in Firefox:**

```bash
# Firefox stores cookies as PLAINTEXT SQLite — no decryption needed
ls ~/Library/Application\ Support/Firefox/Profiles/

sqlite3 ~/.../cookies.sqlite \
  "SELECT host, name, value FROM moz_cookies WHERE host LIKE '%openai.com%'"
```

**Skill auth config:**
```yaml
auth:
  type: browser_session
  browser: firefox          # firefox | chrome | brave | arc | auto
  domain: "openai.com"
  cookie: "__Secure-next-auth.session-token"   # cookie name to extract
```

**Chrome/Brave/Arc** cookies ARE encrypted (SafeStorage pattern, needs Keychain).

---

## Recon Checklist

When investigating a new app:

```bash
# 1. What type of app?
ls /Applications/AppName.app/Contents/Frameworks/ | grep -i electron

# 2. What's in Application Support?
ls ~/Library/Application\ Support/com.company.appname/

# 3. Any JSON config files?
ls ~/Library/Application\ Support/com.company.appname/*.json

# 4. SafeStorage entry?
security find-generic-password -s "AppName Safe Storage" -w

# 5. Any plist settings with auth data?
defaults read com.company.appname 2>/dev/null | grep -i "token\|auth\|account"

# 6. Binary strings for API endpoints and auth patterns:
strings /Applications/AppName.app/Contents/MacOS/AppName \
  | grep -iE "https://api\.|Authorization|Bearer|token|keychain" | head -30

# 7. WebKit storage?
ls ~/Library/WebKit/com.company.appname/ 2>/dev/null

# 8. What Keychain entry type does it use?
# (targeted lookups only, never dump-keychain)
security find-generic-password -s "AppName Safe Storage" -w 2>/dev/null
security find-generic-password -s "com.company.appname" -w 2>/dev/null
```

---

## Known App Auth Patterns

| App | Type | Auth Storage | Readable? |
|-----|------|-------------|-----------|
| Claude Desktop | Electron | SafeStorage + Keychain | ✅ Yes |
| Cursor | Electron | SafeStorage (`Cursor Safe Storage`) | ✅ Yes |
| VS Code | Electron | SafeStorage (`Code Safe Storage`) | ✅ Yes |
| Slack | Electron | SafeStorage (`Slack Safe Storage`) | ✅ Yes |
| Discord | Electron | SafeStorage (`discord Safe Storage`) | ✅ Yes |
| Arc | Electron | SafeStorage (`Arc Safe Storage`) | ✅ Yes |
| ChatGPT Desktop | Native Swift | Keychain Group (`2DC432GLL2.group.com.openai.chat`) | ❌ No |
| Firefox cookies | Browser | Plaintext SQLite | ✅ Yes |
| Chrome cookies | Browser | Encrypted SQLite + Keychain | ⚠️ Needs Keychain |

---

## Key Principle

**Never use broad commands** that trigger system security prompts:
- ❌ `security dump-keychain` — prompts for every app
- ❌ `find ~/Library ...` — prompts for protected directories
- ✅ `security find-generic-password -s "exact service name" -w` — targeted, one prompt
- ✅ `defaults read com.company.appname` — safe, no prompts
- ✅ `strings /Applications/App.app/...` — safe, reads binary
- ✅ `sqlite3 /path/to/specific.sqlite "SELECT ..."` — safe if path is known
