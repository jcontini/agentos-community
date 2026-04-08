# AgentOS Community

Community skills and themes for [AgentOS](https://github.com/jcontini/agentOS-core).

---

## What is AgentOS?

**AgentOS is the semantic layer between AI assistants and your digital life.**

Your tasks are in Todoist. Your calendar is in Google. Your messages are split across iMessage, WhatsApp, Slack. Each service is a walled garden. AgentOS gives AI assistants a unified way to access all your services through a universal entity model.

---

## What's Here

```
skills/            Skills — YAML configs + Python helpers
themes/            UI themes
```

Browse `skills/` for all available skills.

---

## Documentation

All developer documentation lives in the [agentOS SDK repo](https://github.com/jcontini/agent-sdk):

| What | Where |
|------|-------|
| **Skill development guide** | `agentos-sdk/skills-sdk/agentos/GUIDE.md` |
| **Shapes, connections, auth** | `agentos-sdk/docs/` |
| **Reverse engineering** | `agentos-sdk/docs/reverse-engineering/` |
| **Quick reference** | `agentos.to/skills.md` |

---

## Contributing

**Anyone can contribute.** Found a bug? Want a new skill? Have an idea? [Open an issue](https://github.com/jcontini/agentos-community/issues).

```bash
git clone https://github.com/jcontini/agentos-community
cd agentos-community
npm install    # sets up pre-commit hooks
```

Useful commands:

```bash
npm run validate -- exa
npm run lint:semantic -- exa
npm run mcp:call -- --skill exa --tool search --params '{"query":"rust","limit":1}'
npm run mcp:test -- exa --verbose
```

---

## License

**MIT** — see [LICENSE](LICENSE).

By contributing, you grant AgentOS the right to use your contributions in official releases, including commercial offerings. Your code stays open forever.
