# Principles

The laws of the codebase. Every change is evaluated against these.

## 1. Rust is a generic engine

The Rust code knows about *entities*, *relationships*, *schemas*, and *operations*. It never knows about "tasks", "messages", "people", or any specific entity type. **Zero entity-specific or relationship-specific code in Rust.** Hard no.

If you see any of these in Rust, **raise it immediately** — it's a bug in the architecture:
- Hardcoded field names (`priority`, `done`, `blocks`, `blocked_by`)
- Grouping, sorting, or partitioning logic for specific entity types
- Display/formatting/rendering decisions for specific entity types
- Conditional branches on entity type names
- Bespoke data-fetching functions for specific entity types

**CRITICALLY IMPORTANT: If you encounter any of these violations — in any file, for any reason — stop what you're doing and raise it with the user. Do not build on top of a violation. Do not improve it. Delete it. The correct action when you see entity-specific Rust code is deletion, not refactoring.**

**Where specific behavior belongs:**

| Layer | Responsibility | Format |
|-------|---------------|--------|
| Entity schemas | Properties, validation, display hints, sort order, operations | DB (`_type` entities) |
| Templates | Rendering, layout, grouping, formatting | MiniJinja markdown |
| Skills | API mappings, field transforms | YAML |

## 2. Templates do the work

Rendering is never the Rust code's job. Rust provides **small, composable filters** — `listing`, `table`, `tree`, `props`. Templates compose them. Layout decisions live in templates, never in Rust.

A filter should do **one thing**. If a filter is making layout decisions (choosing headings, grouping by priority, separating done/not-done), it's too big. Break it up.

## 3. Foundation first

The most foundational work that prevents tech debt, always. If you're choosing between a feature and fixing an abstraction, fix the abstraction.

## 4. The graph is the source of truth

Every entity modeled correctly, every relationship captured. Skills sync data in; the graph is the authority for reads.

## 5. We have infinite time

No customers, no deadlines, no shortcuts. Do it right or don't do it.

## 6. Co-CTOs

Present the hard design question, decide together. Don't make big architectural choices silently.

## 7. Pain-driven

If you can't articulate the pain, don't build it.

## The Campsite Rule

Leave every module better than you found it. Before writing code, ask yourself: **Is anything bugging me about these abstractions, naming, or architecture?** If yes — tell the user. Propose the cleanup before moving forward.
