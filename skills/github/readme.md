# GitHub

GitHub via the local `gh` CLI. This skill is intentionally scoped to high-signal workflows that are useful from AgentOS today: issues as `task` entities, pull request utilities, and repository file reads as `document` entities.

## Requirements

- Install the GitHub CLI: `brew install gh`
- Authenticate once with `gh auth login`
- Public repository reads often work without login, but issue and PR mutations generally require auth

## What Maps Cleanly

- GitHub issues map to `task`
- Repository files map to `document`
- Pull requests stay inline utility results for now

## Recommended Workflow

1. Use `list_tasks` or `get_task` when you want GitHub issues to flow through the normal task shape.
2. Use `list_documents` and `read_document` for lightweight repo browsing or to inspect a single file without cloning.
3. Use `list_pull_requests` and `create_pull_request` when you need PR metadata or creation, but do not need a first-class PR entity yet.

## Notes

- `read_document` is best for text files tracked in the GitHub contents API.
- Large binaries, LFS-backed objects, and directories that require tree traversal are out of scope for this first pass.
- This skill relies on whatever account and host configuration your local `gh` installation already uses.
