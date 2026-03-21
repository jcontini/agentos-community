# Helper Files & Patterns

## Helper files

Keep skill YAML readable. When executor logic starts looking like real code, extract it into a helper file in the skill folder and have the operation call that file.

Keep in `readme.md` (markdown only — narrative, setup, examples):

- when to use the skill, limitations, and agent-facing notes
- short examples and troubleshooting

Keep in `skill.yaml`:

- `id`, `name`, `connections`, `adapters`, `operations`, executors, and all machine-readable wiring

Move into helper files:

- long AppleScript, Swift, Python, or shell logic
- anything with loops, branching, string escaping, or manual JSON construction
- anything large enough that syntax highlighting, direct local execution, or isolated debugging would help

Preferred patterns:

- use `Swift` helper files for Apple framework integrations like Contacts, EventKit, or other native macOS APIs
- use `Python` helper files for parsing, normalization, and API glue — prefer `python:` executor over `command:` + `binary: python3`
- use `bash` only for thin wrappers or simple pipelines
- keep `AppleScript` inline only when it is truly short; otherwise prefer a helper file

## Leading examples

| Skill | Pattern | File |
|-------|---------|------|
| `gmail` | `_call` dispatch: list stubs then hydrate | `gmail.py` |
| `goodreads` | GraphQL discovery, Apollo cache extraction, multi-tier runtime config | `public_graph.py` |
| `claude` | API replay with session cookies and stealth headers | `claude-api.py` |
| `austin-boulder-project` | Bundle config extraction and tenant-namespace auth | `abp.py` |
| `exa` | Dashboard auth flows, `__secrets__` import, Playwright→HTTPX pattern | (in progress) |
| `reddit` | Shell helper for comment posting | `comments_post.sh` |
| `apple-contacts` | Swift helpers for native macOS APIs | `accounts.swift`, `get_person.swift` |

## Advanced patterns

This book does not try to document every executor or every edge case. If you need something advanced, copy an existing skill:

- `linear` for GraphQL with connections
- `youtube` for command execution
- `gmail` + `mimestream` for provider-sourced OAuth and `_call` dispatch
- `claude` + `brave-browser` for consumer/provider cookie patterns
- `goodreads` for multi-connection (graphql + web) and sandbox storage
- `granola` for multi-connection (API + cache) with Python connection dispatch
- `exa` (in progress) for dashboard auth flows, `__secrets__` secret import, and the Playwright→HTTPX discovery pattern
- an existing cookie-provider skill for keychain, crypto, and multi-step extraction

For skills that reverse-engineer web services without public APIs, see the [Reverse Engineering](../reverse-engineering/overview.md) section.
