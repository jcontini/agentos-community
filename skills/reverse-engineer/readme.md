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
├── Chromium-based (custom browser) → Chrome-style encrypted Cookies → READABLE ✅ (if Safe Storage key found)
├── Native Swift/SwiftUI → Keychain Group (team-signed) → BLOCKED ❌
├── Native Cocoa/ObjC → Varies (Keychain or plist) → INVESTIGATE
└── Web wrapper (WKWebView) → WebKit cookie storage → INVESTIGATE
```

## Two Questions Worth Asking Early

**Can I just use Firefox?**
If the service has a web login and the user can log in via Firefox, the session cookie
is stored plaintext in `cookies.sqlite`. This is almost always easier than reverse
engineering the desktop app. Check this first.

**Is `securityd` pausing/modifying an option?**
No. `securityd` is the macOS security daemon and is fully protected by SIP
(System Integrity Protection). Even root cannot kill, pause, or inject into it.
Attempting to do so would break all auth system-wide.

**Can Keychain Scripting automate a single password reveal?**
`Keychain Scripting.osax` (the AppleScript extension) was removed in macOS Catalina (10.15).
The modern Keychain Access app does not support scripting. Its "Show Password" dialog
specifically blocks UI automation — it requires real user interaction (Touch ID or password).
One manual reveal is the only option, which you'd then paste into AgentOS credentials.

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

### Chromium-Based Apps (Chrome-style Cookies) ✅ READABLE

**Examples:** ChatGPT Atlas, Arc (also has Electron SafeStorage), any custom Chromium shell

**How it works:**
- Uses the same encrypted `Cookies` SQLite DB as Chrome
- Cookies encrypted with AES-128-CBC, PBKDF2-derived key from a Keychain entry
- Key is usually stored as `"{AppName} Safe Storage"` OR `"Chrome Safe Storage"` in Keychain
- Cookie values start with `v10` prefix

**Steps:**
```bash
# 1. Find the Cookies database (in the Chromium profile)
ls ~/Library/Application\ Support/{bundle-id}/browser-data/host/Default/Cookies
ls ~/Library/Application\ Support/{bundle-id}/browser-data/host/{profile}/Cookies

# 2. Check cookie names
sqlite3 /tmp/cookies-copy.db \
  "SELECT host_key, name, length(encrypted_value) FROM cookies WHERE host_key LIKE '%target.com%'"

# 3. Find the Safe Storage key - try AppName and "Chrome Safe Storage":
security find-generic-password -s "{AppName} Safe Storage" -w
security find-generic-password -s "Chrome Safe Storage" -w    # Chromium fallback

# 4. Decrypt (v10 format):
# PBKDF2-HMAC-SHA1(password=key, salt="saltysalt", iterations=1003, dklen=16)
# AES-128-CBC(iv=b'\x20'*16), strip 3-byte "v10" prefix
```

**Important:** Always copy the Cookies DB to /tmp before querying — Chrome locks it while running.

---

### Native macOS Apps (Keychain Groups) ❌ BLOCKED

**Examples:** ChatGPT Desktop

**How it works:**
- Auth library: Auth0 + SimpleKeychain (same as iOS)
- Token stored in Apple Keychain Sharing Group tied to Apple Developer Team ID
- Format: `{TEAM_ID}.group.{bundle-id}` (e.g. `2DC432GLL2.group.com.openai.chat`)
- Actual token lives in `{TEAM_ID}.com.company.shared` (shared cross-app group)
- Only apps signed with the same Team ID can access — enforced by Secure Enclave
- `security` CLI uses legacy SecKeychain API and **cannot even see** data protection keychain items
- Even root cannot bypass this — it's hardware-enforced, not permission-based

**Detection:**
```bash
# Find team-id Keychain groups in binary
strings /Applications/AppName.app/Contents/Frameworks/AppName.framework/AppName \
  | grep -E "[A-Z0-9]{10}\.group\."
```

If you see `XXXXXXXXXX.group.com.company.app` → this is a Keychain Group → blocked.

**Why even root can't help:**
The Secure Enclave holds the encryption key for data protection class `ck` items.
It only releases the key to processes presenting the correct team-signed entitlement.
Root is a Unix concept; the Secure Enclave doesn't care about Unix permissions.

**What CAN see these items:**
- Keychain Access.app — has a private Apple `"*"` wildcard entitlement (only Apple-signed binaries can hold this)
- The app itself — runs in its own process context with the correct entitlement
- `lldb` attached to the app process (requires SIP disabled)

**Keychain item names for ChatGPT Desktop** (for targeted prompts):
```
com.openai.chat.auth
com.openai.chat.account_data_store
com.openai.chat.user_data_store
com.openai.chat.conversations_v2_cache
com.openai.chat.desktop_context_keychain_service
```

**Alternatives:**
- Use the official API with a user-provided API key
- Check if the service has a web login in Firefox → browser cookies (cleanest)
- SIP disable + `lldb -n AppName` → inject `SecItemCopyMatching` call inside process context
- One manual Keychain Access reveal (user clicks "Show Password", approves Touch ID)

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

| App | Type | Auth Storage | Readable? | Safe Storage Key |
|-----|------|-------------|-----------|-----------------|
| Claude Desktop | Electron | SafeStorage JSON config | ✅ Yes | `Claude Safe Storage` |
| Cursor | Electron | SafeStorage | ✅ Yes | `Cursor Safe Storage` |
| VS Code | Electron | SafeStorage | ✅ Yes | `Code Safe Storage` |
| Slack | Electron | SafeStorage | ✅ Yes | `Slack Safe Storage` |
| Discord | Electron | SafeStorage | ✅ Yes | `discord Safe Storage` |
| Arc | Electron | SafeStorage | ✅ Yes | `Arc Safe Storage` |
| ChatGPT Atlas | Chromium | Chrome-style Cookies SQLite | ⚠️ Investigate | `ChatGPT Atlas Safe Storage` or `Chrome Safe Storage` |
| ChatGPT Desktop | Native Swift | Keychain Group (Secure Enclave) | ❌ No | n/a — team-signed only |
| Firefox cookies | Browser | Plaintext `cookies.sqlite` | ✅ Yes | n/a |
| Chrome cookies | Browser | Encrypted `Cookies` SQLite | ⚠️ Needs Keychain | `Chrome Safe Storage` |

**ChatGPT Desktop — what we know:**
- Auth: Auth0 OAuth via `auth0.openai.com`, token type `Authorization-Id-Token`
- API: `https://ios.chat.openai.com` (iOS endpoint), also `chatgpt.com/backend-api/`
- Keychain group: `2DC432GLL2.com.openai.shared` (12 encrypted items found)
- Cert pinning: 10 hardcoded SHA256 public key hashes, custom URLProtocol class
- Hardened Runtime: YES — blocks dylib injection
- Conversation files: AES-encrypted `.data` files, key in `com.openai.chat.conversations_v2_cache`

---

## Key Principle

**Never use broad commands** that trigger system security prompts:
- ❌ `security dump-keychain` — prompts for every app
- ❌ `find ~/Library ...` — prompts for protected directories
- ✅ `security find-generic-password -s "exact service name" -w` — targeted, one prompt
- ✅ `defaults read com.company.appname` — safe, no prompts
- ✅ `strings /Applications/App.app/...` — safe, reads binary
- ✅ `sqlite3 /path/to/specific.sqlite "SELECT ..."` — safe if path is known
