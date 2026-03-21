# Reverse Engineering

How to build skills against web services that don't have public APIs. This is the methodology for extracting data surfaces, auth flows, and content from any website — then packaging them as reliable AgentOS skills.

## The layers

Each layer builds on the previous. Start at transport, work up.

| Layer | What it covers | When you need it |
|-------|---------------|-----------------|
| [1. Transport](1-transport/index.html) | TLS fingerprinting, WAF bypass, Playwright stealth, HTTP/2 | Service blocks automated requests |
| [2. Discovery](2-discovery/index.html) | Next.js/Apollo caches, JS bundle config, GraphQL schema scanning | Finding API endpoints and data shapes |
| [3. Auth & Runtime](3-auth/index.html) | Session cookies, Cognito, cache+discovery+fallback, credential bootstrap | Logging in and managing session state |
| [4. Content](4-content/index.html) | Pagination, infinite scroll, content extraction | Scraping actual data from pages |
| [5. Social Networks](5-social/index.html) | Social graph traversal, friend lists, activity feeds | Working with social platforms |
| [6. Desktop Apps](6-desktop-apps/index.html) | Electron asar extraction, native app IPC, plist configs | Local apps without web APIs |
| [7. MCP Servers](7-mcp/index.html) | Wrapping existing MCP servers as skills | When someone already built an MCP server |

## Core principle

**Playwright discovers, HTTPX runs.**

Use the [Playwright skill](https://github.com/jcontini/agentos-community/tree/main/skills/playwright) to investigate — walk through login flows, capture network requests, inspect DOM structure. Then implement what you learned as Python + `httpx` in the skill. No browser at runtime.

The progression:

1. **Search** — check `web_search` for prior art, existing docs, API references.
2. **Discover** — use Playwright to probe the live site: `inspect`, `capture_network`, `evaluate`.
3. **Replay** — reproduce what you found with HTTPX + cookies. Verify it works.
4. **Implement** — write the skill operation in Python with HTTPX. No browser dependency.
5. **Test** — `test-skills.cjs` runs without a browser. If your skill needs Playwright at runtime, reconsider.

See [Auth & Runtime](3-auth/index.html) for the full methodology on credential flows and the Playwright→HTTPX pattern.

## Starting a new reverse-engineered skill

```bash
npm run new-skill -- my-service

# Then start investigating:
# 1. Open the service in Playwright
# 2. capture_network to find API endpoints
# 3. inspect to understand page structure
# 4. Document what you find in requirements.md
# 5. Implement with httpx in Python
```

For detailed examples, see each layer's documentation. Real-world reference implementations:

- `skills/goodreads/` — multi-tier discovery, Apollo cache extraction, auth boundary mapping
- `skills/claude/` — cookie-based auth, Cloudflare stealth, API replay
- `skills/amazon/` — HTML identity resolution, session cookies, WAF handling
- `skills/austin-boulder-project/` — JS bundle config extraction, tenant-namespace auth
