# Shell History — Skill for AI Agents

How to query, parse, and extract context from shell history (zsh, bash). Use when the user asks about past commands, wants to see comment-leading commands, or needs to understand what was run and when.

---

## Quick Reference

**History file:** `~/.zsh_history` (zsh) or `~/.bash_history` (bash)

**Format (zsh):** `: timestamp:duration;command`
- Multi-line commands use `\` + newline continuation
- Timestamp is Unix epoch (seconds since 1970)

---

## What You Can Extract

| Need | Approach |
|------|----------|
| Commands that start with `#` (comment) | Parse for `cmd.strip().startswith("#")` |
| Date when command ran | `timestamp` field → `datetime.fromtimestamp(ts)` |
| Full command (including continuations) | Join lines until next `: \d+:\d+;` entry |
| Last N comment-leading commands | Parse all, filter, take last N |

---

## Python Parser (Recommended)

Use this when you need date + full command + comment together:

```python
import re
from datetime import datetime

with open(os.path.expanduser("~/.zsh_history"), "r", encoding="utf-8", errors="replace") as f:
    content = f.read()

entries = []
current = None
for line in content.split("\n"):
    m = re.match(r"^: (\d+):\d+;(.*)$", line)
    if m:
        if current and current["cmd"].strip().startswith("#"):
            entries.append(current)
        ts, cmd = m.groups()
        current = {"ts": int(ts), "cmd": cmd}
    elif current is not None:
        current["cmd"] += "\n" + line.rstrip("\\")

if current and current["cmd"].strip().startswith("#"):
    entries.append(current)

# Last 20 comment-leading commands
for e in entries[-20:]:
    dt = datetime.fromtimestamp(e["ts"]).strftime("%Y-%m-%d %H:%M")
    cmd = e["cmd"].replace("\\\n", "\n").strip()
    print(f"=== {dt} ===")
    print(cmd[:600] + ("..." if len(cmd) > 600 else ""))
    print()
```

---

## Shell-Only (No Python)

For quick grep of comment-leading lines (no date, no full command):

```bash
LC_ALL=C grep -oE ';[[:space:]]*#[^\\]+' ~/.zsh_history 2>/dev/null | \
  sed 's/^;[[:space:]]*//' | tail -r | awk '!seen[$0]++' | head -20
```

---

## Notes

- **Encoding:** Use `errors="replace"` or `LC_ALL=C` — history can have invalid UTF-8.
- **Scope:** `~/.zsh_history` is the user's main shell history. Cursor's terminal may have separate history.
- **Comments in commands:** When you run a command with `# comment` at the start, that comment is stored in history. The user can see your reasoning if they inspect the command.
- **Multi-line:** zsh_history joins continuation lines with `\` at end. Strip `\` and join with newline for full command.
