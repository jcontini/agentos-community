# X (Twitter) Adapter Research

**Date:** 2026-02-12
**Status:** Research complete, ready to prototype
**Goal:** Access your own Twitter/X data — posts, followers, following, engagement

---

## Summary of Findings

There are three viable paths to accessing your own Twitter data. The **internal GraphQL API** (what x.com itself uses) is by far the most capable — it gives you everything the official paid API locks behind Enterprise pricing, using your own browser session.

| Approach | Posts | Followers (full) | Following (full) | When followed | Cost | Maintenance |
|----------|-------|-------------------|-------------------|---------------|------|-------------|
| **Internal GraphQL API** | Full history | Full profiles | Full profiles | Never exposed | Free | Medium (libraries handle churn) |
| **X Data Archive** | Full history | IDs only | IDs only | Never exposed | Free | None (one-time) |
| **Official API** | 3,200 max | Enterprise only | Enterprise only | Never exposed | $200-5K/mo | Low |

**"When followed" does not exist anywhere** — not in the API, archive, or any export. Confirmed across dev community.

---

## Path 1: Internal GraphQL API (Recommended)

### What It Is

Twitter's web client (x.com) communicates with the server via a private GraphQL API at `x.com/i/api/graphql/{queryId}/{operationName}`. This is NOT the official developer API — it's the same API your browser calls when you scroll your timeline.

### Authentication

Just two browser cookies:
- **`auth_token`** — your login session (hex string, e.g. `a1b2c3...f4e5d6`)
- **`ct0`** — CSRF token (longer hex string). Also sent as `x-csrf-token` header. **Per-session, NOT per-request.**

Plus a **public bearer token** hardcoded in x.com's JS bundle:
```
AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA
```
This is the same for every user. It just means "I'm the web client."

### Available Endpoints

From [fa0311/TwitterInternalAPIDocument](https://github.com/fa0311/TwitterInternalAPIDocument) (647 stars, auto-updated daily):

| Endpoint | What You Get |
|----------|-------------|
| `UserTweets` | Your posts (tweets, replies, retweets) |
| `Followers` | Your followers list (full user objects with handle, name, bio, counts) |
| `Following` | Who you follow (full user objects) |
| `BlueVerifiedFollowers` | Verified followers specifically |
| `UserByScreenName` | User profile by handle |
| `UserByRestId` | User profile by numeric ID |
| `BlockedAccountsAll` | Blocked accounts |
| `BookmarkSearchTimeline` | Your bookmarks |
| `Likes` | Posts you liked |

### The x-client-transaction-id Challenge

Twitter requires an `x-client-transaction-id` header on GraphQL requests. It is:
- **Generated per-request** from: URL path + HTTP method + timestamp + a SHA-256 hash
- **Seeded by** a key embedded in x.com's HTML (`<meta>` tag) and a daily-changing obfuscated JS file (`ondemand.s`)
- **Not fakeable** — Twitter validates it server-side

The algorithm (from deobfuscated `ondemand.s`):
1. Read seed bytes from `<meta name="tw..." content="...">` tag on x.com homepage
2. SHA-256 hash of `"{method}!{path}!{timestamp}obfiowerehiring{dom_fingerprint}"`
3. Combine: random byte + seed + timestamp bytes + first 16 hash bytes + WebRTC fingerprint + `[3]`
4. XOR and base64 encode

**Libraries handle all of this automatically.** You never need to implement it yourself.

### Ecosystem of Libraries

The same developer (fa0311) maintains a full ecosystem:

| Repo | Stars | What |
|------|-------|------|
| [TwitterInternalAPIDocument](https://github.com/fa0311/TwitterInternalAPIDocument) | 647 | Raw API docs, auto-updated daily from x.com JS |
| [twitter-openapi](https://github.com/fa0311/twitter-openapi) | 176 | OpenAPI 3.0 spec generated from the internal API |
| [twitter-openapi-typescript](https://github.com/fa0311/twitter-openapi-typescript) | 213 | TypeScript client. **License: AGPL-3.0** |
| [twitter_openapi_python](https://github.com/fa0311/twitter_openapi_python) | 93 | Python client. **License: AGPL-3.0** |
| [twitter-tid-deobf-fork](https://github.com/fa0311/twitter-tid-deobf-fork) | 66 | Daily deobfuscation of `ondemand.s` |
| [XClientTransaction (Python)](https://github.com/isarabjitdhiman/xclienttransaction) | 195 | Standalone transaction ID generator. **License: MIT** |

**TypeScript library usage:**
```typescript
import { TwitterOpenApi } from 'twitter-openapi-typescript';

const api = new TwitterOpenApi();
const client = await api.getClientFromCookies({
  ct0: '...',
  auth_token: '...',
});

// Guest mode for public data (no auth):
const guest = await api.getGuestClient();
const user = await guest.getUserApi().getUserByScreenName({ screenName: 'elonmusk' });
```

**Python transaction ID generation (MIT):**
```python
from x_client_transaction import ClientTransaction

home_page = session.get("https://x.com")
ondemand_url = get_ondemand_file_url(home_page_response)
ondemand = session.get(ondemand_url)

ct = ClientTransaction(home_page_response, ondemand_file_response)
tid = ct.generate_transaction_id(method="GET", path="/i/api/graphql/.../UserTweets")
```

### GraphQL Response Structure

Responses are deeply nested:
```
data.user.result.timeline_v2.timeline.instructions[].entries[].content.itemContent.tweet_results.result
```

Each tweet result:
```json
{
  "rest_id": "...",
  "legacy": {
    "full_text": "...",
    "created_at": "Wed Jan 01 00:00:00 +0000 2025",
    "favorite_count": 42,
    "retweet_count": 5,
    "reply_count": 3,
    "bookmark_count": 1
  },
  "core": {
    "user_results": {
      "result": {
        "rest_id": "...",
        "legacy": {
          "screen_name": "handle",
          "name": "Display Name",
          "profile_image_url_https": "..."
        }
      }
    }
  }
}
```

For followers/following, user objects:
```json
{
  "rest_id": "123456",
  "legacy": {
    "screen_name": "handle",
    "name": "Display Name",
    "description": "Bio text",
    "followers_count": 100,
    "friends_count": 50,
    "profile_image_url_https": "https://pbs.twimg.com/...",
    "verified": false,
    "created_at": "..."
  }
}
```

### Risks

**For personal, low-volume, read-only access to your own data:**
- Low risk. Indistinguishable from normal browser usage.
- ~900 requests per 15-minute window for authenticated users.
- Sessions last weeks/months if you don't log out.

**What could cause issues:**
- High volume scraping (hundreds of requests per minute)
- Scraping other people's data at scale
- queryIds rotate every 2-4 weeks (libraries handle this)
- Feature flags change when Twitter ships features (libraries handle this)

### Captured Request (Example)

From Firefox DevTools, a `UserTweets` call:
```
GET https://x.com/i/api/graphql/{queryId}/UserTweets
  ?variables={userId, count, cursor, ...}
  &features={large blob of boolean feature flags}

Headers:
  authorization: Bearer AAAA... (public, hardcoded)
  cookie: auth_token=...; ct0=...
  x-csrf-token: {ct0 value}
  x-twitter-auth-type: OAuth2Session
  x-twitter-active-user: yes
  x-client-transaction-id: {per-request generated}
```

---

## Path 2: X Data Archive

**How:** Settings → Data and permissions → Your X data → Request data (takes a few days)

**Format:** ZIP with `.js` files (JavaScript assignment format):
```javascript
window.YTD.following.part0 = [ {
  "following" : {
    "accountId" : "123456789",
    "userLink" : "https://twitter.com/intent/user?user_id=123456789"
  }
}, ... ]
```

**What you get:**
- Full post history, follower IDs, following IDs, blocked/muted, profile info
- **Only numeric IDs** — no screen names. Need GraphQL API or Nitter to resolve.
- One-time snapshot, not live

**Useful as:** Fallback or supplement. Could be used to seed the graph and then enrich with GraphQL API.

---

## Path 3: Official X API

**Not recommended for this use case.**

| Tier | Cost | Posts | Followers/Following |
|------|------|-------|---------------------|
| Free | $0 | 100 reads/mo | No |
| Basic | $200/mo | 10K reads/mo | Unclear (may need Enterprise) |
| Pro | $5K/mo | 1M reads/mo | Unclear |
| Enterprise | Custom | Custom | Yes |

---

## Adapter Design

### Entities

Both already exist in AgentOS:
- **`post`** (extends document) — tweets, replies, retweets
- **`account`** — platform identity (NOT person, per CONTRIBUTING.md)

### Auth

```yaml
auth:
  type: api_key
  label: "Session Cookies (auth_token:ct0)"
```

Compound key split with `.auth.key | split(":") | .[0]` (Porkbun pattern).

Or `type: cookies` once that's supported (Instagram pattern in `.needs-work/`).

### Seed

```yaml
seed:
  - id: x
    types: [product]
    name: X (Twitter)
    data:
      product_type: platform
      url: https://x.com
      launched: "2006"
      platforms: [web, ios, android]
      wikidata_id: Q918
    relationships:
      - role: offered_by
        to: x-corp

  - id: x-corp
    types: [organization]
    name: X Corp
    data:
      type: company
      url: https://x.com
      founded: "2023"
      wikidata_id: Q117251904
```

### Entity Mappings

```yaml
adapters:
  post:
    terminology: Post
    mapping:
      id: .rest_id
      content: .legacy.full_text
      url: '"https://x.com/" + .core.user_results.result.legacy.screen_name + "/status/" + .rest_id'
      published_at: .legacy.created_at
      engagement.likes: .legacy.favorite_count
      engagement.shares: .legacy.retweet_count
      engagement.comment_count: .legacy.reply_count
      engagement.views: .legacy.views.count
      posted_by:
        account:
          id: .core.user_results.result.rest_id
          platform: '"x"'
          handle: .core.user_results.result.legacy.screen_name
          display_name: .core.user_results.result.legacy.name
          platform_id: .core.user_results.result.rest_id
          url: '"https://x.com/" + .core.user_results.result.legacy.screen_name'

  account:
    terminology: Account
    mapping:
      id: .rest_id
      platform: '"x"'
      handle: .legacy.screen_name
      display_name: .legacy.name
      bio: .legacy.description
      url: '"https://x.com/" + .legacy.screen_name'
      platform_id: .rest_id
      follower_count: .legacy.followers_count
      following_count: .legacy.friends_count
      verified: .legacy.verified
      avatar: .legacy.profile_image_url_https
```

### Operations

```yaml
operations:
  post.list:       # UserTweets GraphQL — your tweets
  account.get:     # UserByScreenName — profile lookup
  account.followers:  # Followers GraphQL — who follows you
  account.following:  # Following GraphQL — who you follow
```

### Implementation Options

**Option A: Use `twitter-openapi-typescript` as dependency (like yt-dlp for YouTube)**
- Add to `requires:` — `npm i twitter-openapi-typescript`
- Shell out to small Node scripts per operation
- Library handles queryId rotation, transaction IDs, feature flags, auth
- **Con:** AGPL-3.0 license

**Option B: Use Python `XClientTransaction` (MIT) + curl**
- `pip install XClientTransaction`
- Generate transaction IDs ourselves, make curl calls
- More control, MIT license, but more code to maintain

**Option C: Roll own curl (not recommended)**
- Hardcode queryIds (break every 2-4 weeks)
- Need to solve transaction ID generation ourselves
- Maximum maintenance burden

**Recommendation:** Option A for prototype speed. Evaluate AGPL implications later. Option B as fallback if AGPL is a problem.

---

## Android Emulator for Reverse Engineering (Bonus Research)

For exploring local databases and MITM-ing app traffic:

| Component | Recommended |
|-----------|-------------|
| **Emulator** | Android Studio AVD (native ARM64 on Apple Silicon) |
| **Root** | rootAVD (Magisk-based, works with Google Play images) |
| **File access** | `adb pull /data/data/<package>/` after root |
| **MITM** | mitmproxy + system CA cert |
| **Cert pinning bypass** | Frida + universal unpinning scripts |

**Setup:** Create AVD (Google Play, API 33-34) → rootAVD → install mitmproxy CA as system cert → set proxy → install Frida for pinned apps.

**Key references:**
- rootAVD: https://gitlab.com/newbit/rootAVD
- mitmproxy Android: https://docs.mitmproxy.org/stable/howto-install-system-trusted-ca-android/
- Frida unpinning: https://gist.github.com/coaxial/f08314685685b14dbce339e57ef51518

---

## Key References

- **Internal API docs (auto-updated daily):** https://github.com/fa0311/TwitterInternalAPIDocument
- **OpenAPI spec:** https://github.com/fa0311/twitter-openapi
- **TypeScript client (AGPL):** https://github.com/fa0311/twitter-openapi-typescript
- **Python client (AGPL):** https://github.com/fa0311/twitter_openapi_python
- **Transaction ID generator (MIT):** https://github.com/isarabjitdhiman/xclienttransaction
- **Transaction ID deobfuscation:** https://github.com/fa0311/twitter-tid-deobf-fork
- **Antibot blog (3-part deep dive):** https://antibot.blog/posts/1741552025433
- **Stack Overflow on x-client-transaction-id:** https://stackoverflow.com/questions/77186145
- **X Data Archive:** https://help.x.com/en/managing-your-account/how-to-download-your-x-archive
