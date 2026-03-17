# iCloud Adapter — Research

> Design research for modeling iCloud Drive (and iCloud services generally) as entity sources in AgentOS. This document captures the deeper design notes; `readme.md` is the clean skill contract.
>
> **Date:** 2026-02-13

The original `.needs-work` draft did the important thinking already. The most useful takeaways for the current top-level skill are:

## What Still Holds

- iCloud Drive is best treated as an entity-importing surface, not a dumb file browser.
- Folder listings are inherently mixed-type and want runtime polymorphism.
- `pyicloud` is the right implementation seam for now because it already handles Apple's session model.
- A saved local session is a much better first-pass integration point than trying to model Apple ID username/password collection directly in skill frontmatter.

## What Changed In This Migration

- The live skill now focuses on iCloud Drive only.
- Files and folders both map through `document` for now.
- The real kind is preserved in `data.kind`.
- Operations are implemented through a small local `pyicloud` wrapper script so the skill can pass the current schema cleanly.

## Future Work

- Add true polymorphic type dispatch for folder listings.
- Promote folders to a first-class place-like entity when that path is ready.
- Expand from Drive into Photos, Contacts, Reminders, or Find My once the Drive path is stable.
