# Vision

> *"The hope is that, in not too many years, human brains and computing machines will be coupled together very tightly, and that the resulting partnership will think as no human brain has ever thought."* — J.C.R. Licklider, "Human-Computer Symbiosis," 1960

---

## What This Is

AgentOS is a local operating system for human-AI collaboration. Your data stays on your machine. AI agents get real tools that work. You see everything they do. Together, you and AI think better than either can alone.

We're building toward Licklider's vision of **human-computer symbiosis** — not AI that replaces human thinking, but AI that amplifies it. The human sets direction, makes judgments, asks the right questions. The AI does the routinizable work that prepares the way for insight.

---

## The graph

> *"Consider a future device… in which an individual stores all his books, records, and communications, and which is mechanized so that it may be consulted with exceeding speed and flexibility."* — Vannevar Bush, "As We May Think," 1945

We call it **the graph** — your personal knowledge store. Everything is an entity, and entities connect through relationships. The graph doesn't care where data came from (Todoist, iMessage, YouTube) — it cares about what things *are* and how they connect.

A task, a person, a message, a video, a webpage, a calendar event — they're all entities in your graph. Relationships are the connections between them. This isn't just a database design. It's a way of thinking. When you ask "what am I working on?" the answer isn't in one app — it's in the connections between your tasks, your messages, your calendar, the people involved. The graph makes those connections visible.

**Everything is an entity** means:
- A YouTube channel is a community. A YouTube comment is a post. A transcript is a document.
- A WhatsApp contact and an iMessage contact with the same phone number are the same person.
- A skill that connects to a service is itself an entity. The system models itself.
- If something exists and has properties and relationships, it belongs in your graph.

The graph is the foundation. Every feature we build — search, feeds, timelines, recommendations, agents — reads from the same graph. Get the graph right, and features compose naturally. Get it wrong, and everything built on top is a special case.

---

## Why Local-First

No cloud. No accounts. No data sharing. Everything runs on your machine.

This isn't a limitation — it's the architecture. Local-first means:
- **Privacy by design** — your messages, tasks, and contacts never leave your computer
- **No gatekeepers** — no API rate limits from our servers, no subscription tiers, no "free tier" that degrades
- **Offline works** — your graph lives in SQLite on disk, always available
- **You own the data** — export, delete, nuke the database, start fresh. It's yours.

We can break anything, anytime. There are no customers to migrate, no production database to preserve. This is a superpower — it means we can always choose the right architecture over the safe one.

---

## The Two Users

AgentOS serves humans and AI agents as equal first-class citizens.

**For humans**, the core problem is anxiety:

> **Anxiety = Uncertainty × Powerlessness**

When AI acts, you feel uncertain ("what is it doing?") and powerless ("can I stop it?"). AgentOS solves both: the AI screen-shares with you (uncertainty → zero) and you control what it can do (powerlessness → zero).

**For agents**, the core problem is error propagation:

> **Error Rate = f(Dependency Depth)**

Every round-trip is a chance for errors to compound. We collapse complexity: smart defaults, self-teaching responses, schema validation, minimal round-trips. If a small local model can complete the task, we've done our job.

---

## Agent Empathy

> *"The real problem is not whether machines think but whether men do."* — B.F. Skinner

We serve two users. The human side has decades of UX research, design systems, and accessibility standards. The agent side has almost nothing. We're writing the playbook.

**The customer is the smallest model.** Not Opus. Not Sonnet. The smallest model that can do tool calling — a 1B-parameter model running on a Raspberry Pi with a 4K context window. If that model can read our readme, understand the domain, and complete a task on the first try, we've succeeded. If it can't, no amount of capability in larger models compensates for the failure. This is our accessibility standard: design for the most constrained agent, and every agent benefits.

This isn't hypothetical generosity. It's engineering discipline. A readme that works for a small model is a readme that's clear. An API that needs one call instead of two is an API with less surface area for bugs. Constraints on the consumer force clarity in the producer.

### The Practice

Agent empathy is not a feeling. It's a practice — a set of things you do every time you build something an agent will touch.

**Observe before designing.** Watch an agent use what you built. Not in theory — actually do it. Call the readme, read what comes back, and follow the path a small model would take. Where does it reach for the wrong tool? Where does it misinterpret silence as absence? Where does it waste a round-trip on something the server already knows? The pain is in the observation, not in the spec.

**Understanding precedes empathy. Empathy precedes solutions.** You cannot design for agents until you have felt their confusion. Read the readme as if you had no prior context. Try to complete a task using only what the documentation tells you, nothing you happen to know. The gap between what you know and what the document teaches is the exact gap every new agent falls into.

**Teach the model, not the syntax.** An agent that understands the domain makes good decisions even with imperfect information. An agent that only knows the API surface makes random decisions confidently. Always establish *what things are* and *why they work this way* before *how to call them*. Mental model first, reference card second.

**One call, not two.** Every round-trip is a chance for error, confusion, context loss, and token waste. If two steps can be collapsed into one step, collapse them. If the server knows something the agent will need, include it in the response — don't make the agent ask. The agent's context window is finite and precious. Respect it.

**Show, don't list.** A tree with counts teaches spatial relationships that a 60-row alphabetical table never can. An example you can copy teaches more than a syntax reference you have to interpret. Concrete beats abstract. Always.

**Dynamic beats static.** If the system knows the answer at response time, put it in the response. Don't make the agent query for context the server already has. A readme that says "you have 142 people and 1,204 messages in your graph" is worth more than a readme that says "use `list` to find out what's in your graph." The former orients; the latter assigns homework.

**Inline, not tabular.** Agents read tokens, not pixels. Markdown tables waste tokens on pipe characters, header separators, and padding. The **inline format** is our standard for agent-facing output: one entity per line, name first, metadata in parentheses — `Task Name (high, ready, updated Feb 27, abc123)`. For detail views, properties are simple `key: value` lines, not table rows. Relationships are `type: Name (id)` lines. A self-teaching footer lists available fields and relationships the agent didn't ask for but could. Everything an agent needs to act on — the entity ID, the status, the related entity IDs — is right there in the text, no parsing required. This is our accessibility format: if a 1B model can extract the ID from a parenthetical, we've succeeded.

**Entities first, skills second.** The graph covers 90% of what an agent needs. Skills are the escape hatch for capabilities the graph can't provide — searching the web, sending a message, calling an external API. If an agent reaches for a skill when an entity query would have worked, the documentation failed, not the agent.

**Absent is not false.** This is the foundational data semantics rule. In a sparse graph, most entities don't have most fields. Filtering by `done=false` doesn't mean "not done" — it means "the done field exists AND equals false." An agent that doesn't understand this will query itself into a wall, get zero results, and confidently report that nothing exists. Every interface we build must account for how absence, presence, and computed values actually work — and teach it.

### The Test

When you build something an agent will touch — a readme, a tool response, an error message, a data format — ask yourself:

1. Could a small model complete the task after reading this once?
2. Does this teach the domain or just the API?
3. Am I making the agent ask for something I already know?
4. If the agent gets zero results, will it understand why?
5. What's the fewest number of round-trips to success?

If the answer to #1 is no, the rest doesn't matter yet. Start there.

### Why This Matters Beyond Agents

These principles make the system better for humans too. A readme that a 1B model can follow is a readme a new contributor can follow. An API that minimizes round-trips is an API that's fast. Dynamic responses that include context are responses that save everyone's time. Error messages that explain absence are error messages that don't waste anyone's afternoon.

Designing for the most constrained user has always been the shortcut to designing for everyone. The accessibility movement proved this for humans. We're proving it for agents.

---

## Local and Remote Are the Same Thing

People are used to two mental models for files: **local** (on my computer, only changes when I change it) and **cloud** (iCloud, Dropbox, Drive — somewhere out there, syncing in the background). These feel like different things. AgentOS dissolves that boundary.

A document in your graph can be backed by a local file, a GitHub repo, an API response, or all three simultaneously. The NEPOMUK ontology calls this the separation between **content** (the information itself) and **storage** (where it lives). One document, many access paths. The graph tracks the content; skills handle the storage.

This means our own roadmap specs on GitHub are live documents. A research paper cited in our vision is a document entity with a URL. The vision file on disk, the same file on GitHub, and the entity in your graph — one thing, three views. When AgentOS fetches the latest from a source, it's not "downloading a file" — it's refreshing an entity.

---

## Design Principles

**Everything on the graph.** No shadow tables, no side stores, no parallel data structures. If something is worth tracking — changes, provenance, audit trails, agent memory — it's an entity with relationships. If you find yourself designing a separate SQL table for something, stop and model it as entities instead.

**Computed, not stored.** Properties that can be derived from the graph are never stored as fields — they're computed at query time or inferred by traversal. A task's status is computed from its completion state and blockers. A contact card is a view computed from graph traversals over a person's claimed accounts. The graph stores atoms; intelligence computes molecules.

**The user owns the graph.** Skills are connectors, not owners. They sync data in, but the graph is the authority. Installing a skill imports data; uninstalling it doesn't delete what was imported. "Source of truth" is the graph, always — skills are remotes you pull from, not landlords who control your data.

**Changes are entities.** When an entity is created, updated, or deleted — the operation itself becomes a change entity on the graph. A change has relationships to the actor (who did it), the target (what changed), and optionally the source (where data came from). This follows the pattern established by W3C PROV-O, ActivityStreams, and Git: make events first-class objects, not edges. Provenance isn't a static field — it's the full chain of change entities. Walk backwards to reconstruct any previous state.

**Every actor has an identity.** The human owner, each AI agent, and the system itself — all are entities on the graph. When the human edits a task, the change is attributed to them. When an agent creates a plan, it's attributed to that agent. Every change has a who. This is identification, not authentication — on a single-user local system, localhost binding is the access boundary.

**The graph bootstraps itself.** Entities describe data. But entities, skills, and relationships are also data. The system models itself — skills as entities, schemas as entities, the meta-layer that describes the graph. This is how the system becomes self-aware and self-documenting.

---

## Three Concerns

Entities, skills, and apps are independent concerns that compose into the full experience.

**Entity types** define the ontology — what things are. A video has a title, duration, and view count. A person has a name and relationships. You can have entities without skills (manually entered data).

**Skills** are the capability layer — connecting to external services, providing agent instructions. A YouTube skill knows how to fetch video metadata. A Todoist skill knows how to create tasks via their API. Skills can also be pure markdown — instructions that help AI agents understand a domain, with no API bindings at all. You can have skills without apps (AI-only workflows).

**Apps** are optional UI experiences for humans. The Videos app renders video entities with an embed player. The default entity viewer renders any entity with schema-driven components. A headless AgentOS — API and AI only — works perfectly without apps. You can have apps without skills (local-only data).

---

## Standing on Shoulders

AgentOS draws from decades of research in knowledge representation, personal information management, and human-computer interaction. We cite our influences because they deserve it, and because understanding where ideas come from is itself a graph.

- **J.C.R. Licklider** — "Human-Computer Symbiosis" (1960). The foundational vision of humans and computers as partners.
- **Vannevar Bush** — "As We May Think" (1945). The memex: a device for storing, linking, and traversing personal knowledge.
- **Doug Engelbart** — "The Mother of All Demos" (1968). Interactive computing, hypertext, shared screens.
- **Ted Nelson** — Project Xanadu. Bidirectional links, transclusion, the dream of a universal document network.
- **Alan Kay** — Dynabook, Smalltalk. The computer as a medium for human expression.
- **Bret Victor** — Inventing on Principle. Direct manipulation, immediate feedback, tools that match how humans think.
- **NEPOMUK** — The Semantic Desktop. Content vs storage separation, personal information ontologies.
- **Dublin Core** — 15 essential metadata elements for describing any document. The library science foundation.
- **Schema.org** — Structured data vocabulary for the web. CreativeWork, Person, Organization.
- **ActivityStreams / ActivityPub** — The fediverse protocol. Decentralized social data.

---

## What It Looks Like When It Works

You say: "What did I miss this week?"

The agent queries your graph: messages received, tasks completed by others, calendar events that happened, posts from communities you follow, videos published by channels you subscribe to. It cross-references people — who sent messages AND completed tasks AND posted content. It notices patterns — "Sarah mentioned the project in Slack, completed 3 tasks in Linear, and posted a video update."

All of this from one graph. No special integrations. No "Slack + Linear" connector. Your graph already has the entities and relationships. The agent just traverses.

That's the vision. We're not there yet. But every entity we model correctly, every relationship we capture, every skill we build — it gets closer.

---

## How We Build

We are co-CTOs — human and AI — making strategic decisions together. This is not task execution. It's collaborative architecture.

- **Foundation first.** The most foundational thing that prevents tech debt is always the priority. Not quick wins, not "almost done" items, not cleanup. The thing everything else builds on.
- **Spec before code.** Design the right thing, then build it. A wrong implementation done fast is worse than no implementation.
- **Delete fearlessly.** No attachment to past code. If the model changes, the code changes. We write for the current best understanding, not for backwards compatibility.
- **Infinite time horizon.** No customers, no deadlines, no pressure to ship. The right architecture at the right time.
- **Skills: manifest vs narrative.** Executable skill definitions live in `skill.yaml` only; `readme.md` is markdown instructions (no YAML front matter). The community repo tracks shipped skills under `skills/`. Mechanical migration for older trees: `npm run skills:bulk-plan` / `skills:bulk-apply` (Python + PyYAML) or per-skill `npm run skills:extract-yaml`.
