# Claude skill — outstanding work

Living TODO list for the consolidated `ai/claude` skill. Crossed off as shipped.

## Migration status (this pass)

- [x] Move `inference/anthropic-api/anthropic-api.py` → `ai/claude/claude_api.py`
- [x] Move `inference/claude/claude-api.py` (misnamed web scraper) → `ai/claude/claude_web.py`
- [x] Move `inference/claude/claude-llm.py` → `ai/claude/claude_code.py`
- [x] Remove hardcoded `MODEL_ALIASES` from `claude_api.py` and `claude_code.py`
- [x] Remove hardcoded `models=[...]` from `@provides(llm, ...)` decorators
- [x] Consolidate `inference/claude/readme.md` + `inference/anthropic-api/readme.md` → `ai/claude/readme.md`
- [x] Delete old `inference/` category (also moved ollama + openrouter to `ai/`)
- [x] **`claude_code.list_models` works end-to-end** — OAuth token from keychain → `/v1/models` → 9 models. Subscription-based, no API key. First-class CLI support.
- [ ] **Rename `op_` prefix on web operations?** `claude_web.py` has `op_list_conversations`, `op_get_conversation`, etc. Other skills use bare names (`search`, `read_webpage`). Decide whether to strip `op_` for consistency.
- [ ] **Verify two `provides: llm` declarations work.** `claude_api.chat` and `claude_code.chat` both `@provides(llm)` from the same skill. Engine should treat them as separate providers of the same capability. Test end-to-end once MCP routing is wired up.
- [ ] **Don't hardcode `ANTHROPIC_VERSION`** — extract it from the Claude Code installation (binary resource or config file) at runtime so it stays current when Claude Code updates.
- [ ] **Make Claude Code an OAuth provider for Claude** — parallel to how Mimestream is an OAuth provider for Google. When present, the `api` connection should be able to auth via Claude Code's keychain token instead of requiring a separate API key.

## Proposals to resolve (carried over from old `inference/claude/readme.md`)

These were **proposals only** in the old readme — no implementation existed. Moved here
as an explicit TODO. Full prior-art text is in `/tmp/old_inference_claude_readme.md`
during this session; to persist, move to `docs/specs/`.

- [ ] **Remote Control via launchd** — `claude remote-control` as a background service
      so agentOS is reachable from phone/browser. Operations proposed:
      `check_claude_code`, `start_remote_control`, `stop_remote_control`,
      `remote_control_status`, `configure_remote_control`.
      **Decision needed:** move proposal to `docs/specs/claude-remote-control.md` and
      link it here, or kill it until there's a concrete ask.

- [ ] **Scheduled Jobs graph tracking** — record `CronCreate`/`RemoteTrigger` jobs as
      `schedule` nodes so agentOS can query/reconcile them. Operations proposed:
      `track_scheduled_job`, `sync_scheduled_jobs`, `untrack_scheduled_job`.
      **Decision needed:** same — promote to spec or park indefinitely.

## New capabilities from the ontology sub-agent (in flight)

The sub-agent running against `~/.claude/` is producing three artifacts in
`_projects/_drafts/`:
1. `claude-code-ontology.md` — node/edge schema for Claude Code local state
2. `claude_code_graph_prototype.py` — standalone Python that emits a graph JSON
3. `claude_code_graph.html` — d3 viz of the graph

When that lands, the local-state ops get implemented in `claude_code.py`:

- [ ] `list_sessions(project=None, since=None, limit=50)` → session[]
- [ ] `get_session(id, include_tool_results=False)` → full transcript
- [ ] `list_subagents(session_id=None, agent_type=None)` → task[]
- [ ] `get_subagent(agent_id)` → transcript + meta
- [ ] `list_prompts(project=None, since=None, limit=100)` — reads `history.jsonl` + `paste-cache/`
- [ ] `list_tasks(session_id=None, status=None)` — reads `tasks/**`
- [ ] `list_plans(query=None)` — reads `plans/*.md`
- [ ] `list_edited_files(session_id)` — reads `file-history-snapshot` events + `file-history/**`
- [ ] `get_file_version(session_id, path, version)`
- [ ] `usage_summary(since=None, until=None, by="day")` — recompute from jsonls (stats-cache is stale)
- [ ] `list_live_instances()` — reads `sessions/*.json` + `ide/*.lock` (redact `authToken`)
- [ ] `list_plugins()` — reads `plugins/installed_plugins.json` + `known_marketplaces.json`
- [ ] `get_settings()` — read-only inspection of `settings.json`/`settings.local.json`

## Cross-skill tasks

- [ ] **Standardize snake_case for Python files** — add convention to
      `agentos-sdk/skills-sdk/agentos/GUIDE.md`. All `.py` files in skills should be
      `snake_case.py` (not `kebab-case.py`). Current codebase is mixed.
- [ ] **Move `web_read` provides** — `op_get_conversation` currently has
      `@provides(web_read, urls=["claude.ai/chat/*", "www.claude.ai/chat/*"])`.
      Verify the URL patterns still match after the skill rename.
- [ ] **Install MCP into Claude Code** — `~/.claude.json` MCP config editing, matching
      the pattern in `dev/cursor/cursor.py`'s `MCP_CONFIG_PATHS` (which already has a
      `# Future: claude-code` placeholder). Extend that or re-implement here.
