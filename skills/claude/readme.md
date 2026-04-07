---
id: claude
name: Claude.ai
description: Claude.ai web chat history — browse and search conversations from your personal claude.ai account
color: "#D97757"
website: "https://claude.ai"
privacy_url: "https://www.anthropic.com/privacy"
terms_url: "https://www.anthropic.com/terms-of-service"

connections:
  cli:
    description: Claude Code binary — auth handled by the binary itself
  web:
    auth:
      type: cookies
      domain: .claude.ai
      names:
      - sessionKey
      account:
        check: check_session
      login:
        account_prompt: What email do you use for claude.ai?
        phases:
        - name: request_login
          description: Submit email on the Claude login page to trigger a magic link email
          steps:
          - action: goto
            url: https://claude.ai/login
          - action: fill
            selector: input[type=email]
            value: ${ACCOUNT}
          - action: click
            selector: button[type=submit]
          returns_to_agent: 'Magic link requested. Check the user''s email for a message from Anthropic

            containing a claude.ai/magic-link URL. Search mail or the graph for that message,

            or ask the user to paste the link.

            '
        - name: complete_login
          description: Navigate to the magic link URL to complete authentication
          requires:
          - magic_link
          steps:
          - action: goto
            url: ${MAGIC_LINK}
          - action: wait
            url_contains: /new
          returns_to_agent: 'Login complete. The sessionKey cookie is now in the browser.

            Cookie provider matchmaking will extract it automatically on the next API call.

            '

product:
  name: Claude
  website: https://claude.ai
  developer: Anthropic

test:
  check_session:
    skip: true
---

# Claude

Claude Code on the user's machine — chat history, remote control, and scheduled jobs.

## Philosophy

AgentOS doesn't build email — it uses Gmail. Doesn't build web search — it uses Exa/Brave.
Same here: AgentOS doesn't build remote control or cron. It tracks shapes, skills do the work.

This skill bridges Claude Code's platform capabilities into AgentOS:

| Capability | Abstract tool | Claude Code feature | Status |
|------------|--------------|---------------------|--------|
| Chat history | `web_read` (claude.ai URLs) | claude.ai API | Done |
| Remote control | `remote_control` | `claude remote-control` | Proposal |
| Scheduled jobs | `cron` | CronCreate / RemoteTrigger | Proposal |

---

## Remote Control

### Problem

AgentOS runs on the user's machine. Away from desk = no access to skills.

### Solution

Claude Code [Remote Control](https://code.claude.com/docs/en/remote-control) lets you drive
a local session from phone/browser. Since Claude Code has MCP access to AgentOS, remote
control of Claude Code = remote control of AgentOS.

```
Phone/Browser → claude.ai/code → Claude Code (local) → AgentOS MCP → all skills
```

No inbound ports. Claude Code polls Anthropic's API over HTTPS. All MCP servers, auth,
and config stay local. Session auto-reconnects after sleep (< ~10 min).

### Proposal: launchd-managed background service

`claude remote-control` is a foreground process — it stays running and outputs a session URL
on stdout. Tested: it skips the confirmation prompt when stdin is `/dev/null` (what launchd
provides), handles SIGTERM gracefully, and does not fork. This is exactly what launchd wants.

**Process management via launchd plist:**

```xml
<!-- ~/.agentos/services/com.agentos.remote-control.plist -->
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.agentos.remote-control</string>
    <key>ProgramArguments</key>
    <array>
        <string>~/.local/bin/claude</string>
        <string>remote-control</string>
        <string>--name</string>
        <string>AgentOS</string>
    </array>
    <key>WorkingDirectory</key>
    <string>~/dev/agentos</string>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key><false/>
        <key>Crashed</key><true/>
    </dict>
    <key>ThrottleInterval</key>
    <integer>10</integer>
    <key>StandardOutPath</key>
    <string>~/.agentos/logs/remote-control.log</string>
    <key>StandardErrorPath</key>
    <string>~/.agentos/logs/remote-control.log</string>
</dict>
</plist>
```

**Lifecycle:**
- `start_remote_control` → write plist, copy to `~/Library/LaunchAgents/`, `launchctl bootstrap`
- `stop_remote_control` → `launchctl bootout`, remove from LaunchAgents
- `remote_control_status` → `launchctl print` + grep log for bridge URL
- Bridge URL extracted from stdout: `https://claude.ai/code?bridge=env_XXXXX`
- Auto-restart on crash via KeepAlive. 10s throttle prevents restart loops.
- Survives terminal close and Mac sleep (suspends/resumes with reconnect).
- Does NOT survive user logout (LaunchAgents limitation — no user-space workaround).

**Alternatives considered:**

| Option | Auto-restart | Survives terminal | Survives logout | Notes |
|--------|-------------|-------------------|-----------------|-------|
| **launchd** (proposed) | Yes | Yes | No | macOS-native, correct tool for the job |
| nohup + PID file | No | Yes | No | Simple but no crash recovery |
| tmux detached | No | Yes | No | Can reattach to see TUI, but overkill |
| Always-on config | N/A | N/A | N/A | `remoteControlAtStartup` in `~/.claude.json` — enables RC for all sessions but no dedicated server |

**Always-on config** (`remoteControlAtStartup: true` in `~/.claude.json`) is complementary,
not a replacement. It makes every interactive Claude Code session remote-accessible, but
only while a session is open. The launchd service provides a dedicated always-on server.
We should support both — `configure_remote_control` toggles the config key,
`start_remote_control` manages the launchd service.

### MCP server registration

AgentOS must be registered as a Claude Code MCP server for remote control to be useful.
Currently configured as a user-scoped stdio server:

```
agentOS: /Users/joe/dev/agentos/target/debug/agentos mcp (user scope, all projects)
```

For other users, the skill should verify and register if missing:
```bash
claude mcp list | grep -q agentOS || claude mcp add agentOS /path/to/agentos mcp -s user
```

### Prerequisites and installation

**Hard requirements for remote control:**
- Claude Code v2.1.51+ (native binary at `~/.local/bin/claude`)
- OAuth login via `claude auth login` (not API key, not setup-token)
- Pro/Max/Team/Enterprise subscription

**Detection** — `claude auth status` returns JSON:
```json
{ "loggedIn": true, "authMethod": "claude.ai", "subscriptionType": "max" }
```
Exit code 0 if logged in, 1 if not. `claude --version` returns e.g. `2.1.87 (Claude Code)`.

**If Claude Code is not installed:**
```bash
curl -fsSL https://claude.ai/install.sh | bash   # native installer, no deps
# or: brew install claude-code                     # homebrew cask
# or: npm install -g @anthropic-ai/claude-code     # requires Node >= 18, deprecated
```

**If not authenticated:**
```bash
claude auth login   # opens browser for OAuth — cannot be fully headless
```

The OAuth step requires a browser interaction once. After that, the session persists and
remote control can be started programmatically. This is a real constraint: AgentOS cannot
fully automate onboarding for a brand-new user without browser access. The skill should
detect this state and guide the user through it.

### Tools

```yaml
tools:
  check_claude_code:
    description: Detect Claude Code installation, auth, and capability status
    returns: { installed, version, authenticated, subscription, remote_control_capable, cron_capable }
    python:
      module: ./claude-rc.py
      function: check_claude_code

  start_remote_control:
    description: Start a Remote Control background service via launchd
    params:
      name: { type: string, default: "AgentOS", description: "Session name shown in claude.ai" }
    returns: { url, status, pid }
    python:
      module: ./claude-rc.py
      function: start_remote_control

  stop_remote_control:
    description: Stop the Remote Control background service
    returns: { stopped }
    python:
      module: ./claude-rc.py
      function: stop_remote_control

  remote_control_status:
    description: Check if Remote Control is active, return bridge URL
    returns: { active, url, pid, uptime }
    python:
      module: ./claude-rc.py
      function: remote_control_status

  configure_remote_control:
    description: Toggle always-on Remote Control for all Claude Code sessions
    params:
      enabled: { type: boolean, required: true }
    returns: { enabled }
    python:
      module: ./claude-rc.py
      function: configure_remote_control
```

### provides declaration

```yaml
provides:
  - tool: remote_control
    via: start_remote_control
    description: "Remote access to AgentOS via Claude Code Remote Control"
```

Uses the existing `ProvidesEntry::Tool` variant — same mechanism as `web_search`. No engine
changes needed. When an agent asks "who provides remote_control?", the engine routes here.

---

## Scheduled Jobs

### Problem

No way to run skills on a schedule. No daily digests, no recurring imports, no hourly checks.

### Solution

Claude Code has three scheduling tiers. AgentOS tracks the shapes; Claude Code runs them.

### Claude Code's scheduling tiers

| Tier | How to create | Runs on | Survives restart | Machine needed | MCP access |
|------|--------------|---------|-----------------|----------------|------------|
| **Session** | `CronCreate` tool, `/loop` | Local process | No (3-day expiry) | Yes | Inherits session |
| **Desktop** | Desktop app UI only | Local (Desktop app) | Yes | Yes | Config files |
| **Cloud** | `/schedule` skill, `RemoteTrigger` tool | Anthropic cloud | Yes | No | Connectors per task |

**Session tier** — `CronCreate(cron, prompt, recurring)` is an in-session tool the agent
already has. 5-field cron expression, fires while session is idle, max 50 jobs, auto-expires
after 3 days. `CronList` and `CronDelete` for CRUD. These are NOT CLI commands — they exist
only inside a running Claude Code session.

**Desktop tier** — managed by Claude Desktop app. Tasks stored at
`~/.claude/scheduled-tasks/<name>/SKILL.md`. Catches up missed runs (checks last 7 days on
wake). No programmatic CLI — requires Desktop app runtime.

**Cloud tier** — `RemoteTrigger` tool with `create`, `list`, `get`, `update`, `run` actions.
Accessible from CLI via `/schedule` skill. Clones repo fresh each run. Minimum 1-hour interval.
Requires claude.ai OAuth.

### Proposal: graph tracking, not wrapping

The skill does NOT wrap CronCreate. The agent already has CronCreate/CronList/CronDelete as
native tools in any Claude Code session. And it has RemoteTrigger for cloud tasks.

The skill's job is:
1. **Track** — record schedule nodes in the graph when the agent creates jobs
2. **Reconcile** — on boot or on demand, compare graph state vs provider state
3. **Report** — surface what's active, stale, or expired

This is the same pattern as email: Gmail sends the email, AgentOS tracks the entity.

### The `schedule` shape

A schedule is **not an event**. Events are things that happen (meetings, concerts).
A schedule is a rule that triggers things. See `shapes/schedule.yaml`:

```yaml
schedule:
  fields:
    schedule_type:     string    # cron, one_shot, interval
    cron_expression:   string    # 5-field (e.g. "0 9 * * *")
    timezone:          string    # IANA timezone
    prompt:            string    # what to do when it fires
    enabled:           boolean
    durability:        string    # session, desktop, cloud
    provider_job_id:   string    # provider's native ID
    last_fired_at:     datetime
    next_fire_at:      datetime
  relations:
    provider:          skill     # which skill runs this
```

### Tools

```yaml
tools:
  track_scheduled_job:
    description: Record a schedule node for a job the agent created via CronCreate or RemoteTrigger
    params:
      provider_job_id: { type: string, required: true }
      cron_expression: { type: string, required: true }
      prompt: { type: string, required: true }
      durability: { type: string, default: "session", description: "session, desktop, or cloud" }
      name: { type: string, description: "Human name for this schedule" }
    returns: schedule
    python:
      module: ./claude-cron.py
      function: track_scheduled_job

  sync_scheduled_jobs:
    description: >
      Reconcile graph schedule nodes against live provider state.
      The agent should call CronList (session) or RemoteTrigger list (cloud) first
      and pass the results here. Returns diff: new, expired, stale.
    params:
      live_jobs: { type: array, required: true, description: "Current jobs from CronList or RemoteTrigger" }
    returns: { new, expired, stale, active }
    python:
      module: ./claude-cron.py
      function: sync_scheduled_jobs

  untrack_scheduled_job:
    description: Remove a schedule node from the graph (after CronDelete or RemoteTrigger delete)
    params:
      provider_job_id: { type: string, required: true }
    returns: { deleted }
    python:
      module: ./claude-cron.py
      function: untrack_scheduled_job
```

### provides declaration

```yaml
provides:
  - tool: cron
    via: track_scheduled_job
    description: "Track scheduled jobs in the AgentOS graph"
```

### Example workflows

**"Summarize my email every morning at 9am":**
1. Agent calls `CronCreate("0 9 * * *", "Use AgentOS gmail to summarize unread emails")`
2. Agent calls `track_scheduled_job(provider_job_id=<id>, cron_expression="0 9 * * *", ...)`
3. Schedule node exists in graph. Boot reports it. Agent can query/delete later.

**"Move that to a cloud task so it runs even when my laptop is off":**
1. Agent calls `CronDelete(<id>)` to remove session job
2. Agent calls `RemoteTrigger create(...)` to create cloud task
3. Agent calls `track_scheduled_job(provider_job_id=<trigger_id>, durability="cloud", ...)`
4. Graph updated. Old session node replaced with cloud node.

---

## Chat History (existing)

Browse and search claude.ai web conversation history. Cookie provider matchmaking resolves
`.claude.ai` cookies → `sessionKey` injection → `httpx` API calls. No browser needed.

| Operation | What it does |
|-----------|-------------|
| `list_conversations` | Browse conversations, most recent first |
| `get_conversation` | Full conversation with all messages |
| `search_conversations` | Search by title (client-side filter) |
| `import_conversation` | Import messages into graph for FTS |
| `list_orgs` | Discover orgs and capabilities |
| `extract_magic_link` | Parse magic link from raw email |

---

## Decisions to make

### D1: Should `start_remote_control` use `__exec__` or subprocess directly?

The executor consolidation is moving toward all subprocess calls routing through
`_call("__exec__", ...)` so the engine can audit and allowlist. But `__exec__` dispatch
isn't built yet (Phase 2 roadmap item). For now, `subprocess.run()` works.

**Proposal:** Use `subprocess.run()` now, migrate to `__exec__` when available.

### D2: What working directory should the remote control server use?

`claude remote-control` needs a working directory. Options:
- **The AgentOS repo** (`~/dev/agentos`) — gives access to project CLAUDE.md
- **Home directory** (`~`) — neutral, but no project context
- **Configurable** — let the user pick

**Proposal:** Default to the AgentOS repo directory (wherever the `agentos` binary lives).
This gives the remote session access to the AgentOS CLAUDE.md and project context.

### D3: How should the skill handle Claude Code not being installed?

For our own machine, Claude Code is already installed. For other users:

**Proposal:** `check_claude_code` detects the state and returns a structured result:
- `not_installed` → return install instructions (one-liner: `curl -fsSL https://claude.ai/install.sh | bash`)
- `installed_not_authenticated` → return: "run `claude auth login` (opens browser)"
- `authenticated_wrong_method` → API key or setup-token won't work, need OAuth
- `ready` → all good, can start remote control

The skill guides but doesn't auto-install. Installation requires user consent (it's a
third-party binary). Auth requires browser interaction (can't automate). This is a
dependency management question that applies to all skills with external deps — not
specific to this skill.

### D4: Permission mode for the remote control server

`claude remote-control` creates sessions that can run tools. What permission mode?

- `bypassPermissions` — fully autonomous, no prompts (dangerous)
- `auto` — Claude's auto-mode classifier decides (Team+ only, Sonnet/Opus only)
- `default` — prompts for dangerous operations (but who sees the prompt remotely?)

**Proposal:** Don't hardcode it. Let the user's existing Claude Code config apply.
The plist doesn't set `--permission-mode`. Whatever the user has configured in their
settings.json (`defaultMode`) applies. If they want bypass, they've already opted in.

### D5: Should `provides: tool: cron` route to `track_scheduled_job` or should it not exist?

The `cron` capability is unusual because the agent doesn't call the skill to create jobs —
it calls CronCreate/RemoteTrigger directly and then tells the skill to track it. This is
different from `web_search` where the skill does the actual work.

Options:
- **A: `provides: tool: cron` routes to `track_scheduled_job`** — the abstract tool exists
  but just records the job. Feels wrong — calling `cron` and getting back a tracking node
  isn't what the caller expects.
- **B: No provides for cron** — the skill has operations but doesn't declare an abstract
  tool. Agents know to use CronCreate directly and call track_scheduled_job after.
- **C: `provides: tool: cron` routes to a wrapper** — the skill calls CronCreate on behalf
  of the agent, then tracks it. Single call does both. But this means wrapping an in-session
  tool from a skill, which is weird.

**Proposal:** Option B for now. The agent uses CronCreate/RemoteTrigger natively and calls
tracking operations explicitly. Later, if we want a unified `cron` tool that abstracts over
providers, we build it as a wrapper operation.

### D6: Log rotation for remote control

The launchd plist appends stdout to `~/.agentos/logs/remote-control.log` forever.

**Proposal:** Truncate the log on each `start_remote_control` call (the old bridge URL is
stale anyway). Or: cap at 1MB and rotate with a simple Python check in the status operation.
Not worth a real log rotation system for a single file.
