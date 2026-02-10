# FRBR Work/Expression Architecture

**Status:** Spec  
**Author:** Keel (AI agent)  
**Date:** 2026-02-10

---

## Executive Summary

AgentOS currently treats video, audio, and document as independent entity types, each with a `creator` property. But these are actually **expressions** of the same underlying **work**. A story can be a book (document), audiobook (audio), and film (video) — all expressions of the same creative work. The creator belongs on the work, not the expression. Different expressions have different performers, translators, narrators.

This spec proposes a comprehensive FRBR (Functional Requirements for Bibliographic Records) architecture that:

1. **Preserves the existing `work` primitive** but enhances it with proper creator/contributor roles
2. **Removes `creator` from expression entities** (video, audio, document)
3. **Uses the existing `references` relationship** with FRBR roles (`expression_of`, `manifestation_of`, `item_of`)
4. **Models contributors through `references` with role-specific relationships** (author, composer, performer, translator, narrator, director, etc.)
5. **Makes FRBR opt-in** — most YouTube videos don't need work entities; works appear when you actually have multiple expressions

---

## Table of Contents

1. [FRBR Primer](#frbr-primer)
2. [Current State Analysis](#current-state-analysis)
3. [Proposed Architecture](#proposed-architecture)
4. [Entity Hierarchy](#entity-hierarchy)
5. [Relationship Types](#relationship-types)
6. [Role Modeling](#role-modeling)
7. [Expression vs Work: When to Create Each](#expression-vs-work-when-to-create-each)
8. [Migration Path](#migration-path)
9. [Adapter Changes](#adapter-changes)
10. [Open Questions](#open-questions)

---

## FRBR Primer

### What is FRBR?

FRBR (Functional Requirements for Bibliographic Records) is a conceptual model developed by IFLA (International Federation of Library Associations) to structure bibliographic information. It defines four levels of abstraction for intellectual and artistic products:

```
Work ────────────> Expression ────────────> Manifestation ────────────> Item
(abstract)         (realization)            (publication)               (copy)
```

### The Four Levels

| Level | Definition | Example (Hamlet) | Example (Music) |
|-------|-----------|------------------|-----------------|
| **Work** | Abstract intellectual/artistic creation | "Hamlet" as a concept | Schubert's Trout Quintet (concept) |
| **Expression** | Specific realization of a work | English text, German translation, 1996 film, audiobook | Original score, Boston Symphony performance, Amadeus Quartet recording |
| **Manifestation** | Physical embodiment/edition | 2003 Penguin paperback, 1996 DVD, 2020 Audible | 1997 Deutsche Grammophon CD, 2010 iTunes download |
| **Item** | Individual copy | My copy with notes in margin | The CD in my collection |

### Why FRBR Matters

**Problem:** Without FRBR, we treat each expression as independent:
- "Hamlet" (English book) has creator: Shakespeare
- "Hamlet" (German audiobook) has creator: ???
- "Hamlet" (1996 film) has creator: Kenneth Branagh

But Shakespeare is the **work creator**. The German translator, audiobook narrator, and film director are **expression contributors** with different roles.

**Solution:** FRBR separates the abstract work from its realizations:
- **Work:** "Hamlet" → creator: William Shakespeare
- **Expression:** English text → no creator (inherits from work)
- **Expression:** German translation → translator: August Wilhelm Schlegel
- **Expression:** 1996 film → director: Kenneth Branagh, actor: Kenneth Branagh
- **Expression:** Audiobook → narrator: Simon Russell Beale

### FRBR Relationships (from official spec)

**Group 1 Entities (Products):**
- Work → Expression (is realized through)
- Expression → Manifestation (is embodied in)
- Manifestation → Item (is exemplified by)

**Group 2 Entities (Agents):**
- Person/Corporate Body → Work (created by, commissioned by, subject of)
- Person/Corporate Body → Expression (realized by, translated by, narrated by, performed by)
- Person/Corporate Body → Manifestation (produced by, published by)
- Person/Corporate Body → Item (owned by, held by)

**Key Insight:** Different contributor roles attach at different levels:
- Author, composer → **Work**
- Translator, performer, narrator, director → **Expression**
- Publisher, producer → **Manifestation**
- Owner → **Item**

### BIBFRAME Consolidation

The Library of Congress developed BIBFRAME 2.0, which consolidates FRBR's four levels to three:

- **Work** (unchanged)
- **Instance** (combines Expression + Manifestation)
- **Item** (unchanged)

**Why this matters for us:** BIBFRAME validated that Expression and Manifestation can be collapsed in practice. For AgentOS, we'll keep all four levels available but make them opt-in through `references` relationships. Most content won't use all levels.

---

## Current State Analysis

### Entity Inventory

**Expression-level entities (have creator):**
- `video` extends `media` — has `creator` in comments but uses `posts` relationship
- `audio` extends `media` — has `creator: references: person` (line 4)
- `recording` extends `media` — has `creator` (line 4)
- `document` — has `author: references: person` (line 37)
- `book` extends `document` — inherits `author`
- `post` extends `document` — inherits `author`
- `webpage` extends `document` — inherits `author`
- `message` — has `sender: references: person` (not creator, delivery semantics)

**Work-level entities:**
- `work` (_primitives/work.yaml) — has `original_creator: references: person`

**Note:** `video` already removed `creator` in favor of `posts` relationship (account --posts--> video). The comment says "Uses `posts` relationship... This replaces the old `creator: references: person`."

### What's Wrong

1. **Creator on expressions, not works:** `audio` and `recording` have `creator`, but if you have a book (document) + audiobook (audio) of the same story, they'd have different creators. The author should be on the work.

2. **No standardized way to link expressions to works:** The `work` entity exists but isn't used. There's no convention for "this video is an expression of this work."

3. **No role differentiation:** `creator` is too generic. The author of a book, narrator of an audiobook, and director of a film are all "creators" but with different roles.

4. **Video already evolved past this:** Video uses `posts` (attribution to account) and can use `references` with roles (director, actor, etc.). This is the right pattern.

5. **Message uses `sender`:** This is correct — messages have delivery semantics, not creation semantics. Not a creator problem.

### What's Right

1. **The `work` primitive exists:** Already defined in `_primitives/work.yaml` with FRBR references
2. **FRBR roles already in `references`:** `expression_of`, `manifestation_of`, `item_of`, `translation_of`, `adaptation_of`, `performance_of` (lines 104-139 of references.yaml)
3. **Credit roles already defined:** `director`, `actor`, `editor`, `producer`, `composer`, `narrator` (lines 288-315 of references.yaml)
4. **Video already uses attribution correctly:** `posts` relationship for observable attribution (account), `claims` for person behind account
5. **Opt-in philosophy:** The work.yaml comment says "Most entities don't need a work. A YouTube video is just a video. Works appear when you actually have multiple representations."

---

## Proposed Architecture

### Core Principles

1. **Schema-first, always** — Entity YAMLs are the source of truth
2. **Composition over hierarchy** — Entities extend and reference each other
3. **Graph as truth** — Relationships via `references`, not properties
4. **Opt-in FRBR** — Most expressions don't need work entities
5. **Observable attribution** — Use what we can actually observe (accounts, platforms)
6. **Roles for specificity** — Use `references` with roles, not generic creator

### High-Level Design

```
                                 ┌─────────────┐
                                 │    Work     │
                                 │  (abstract) │
                                 └──────┬──────┘
                                        │
                  ┌─────────────────────┼─────────────────────┐
                  │                     │                     │
            ┌─────▼─────┐         ┌─────▼─────┐       ┌─────▼─────┐
            │ Expression│         │ Expression│       │ Expression│
            │  (text)   │         │  (audio)  │       │  (video)  │
            └───────────┘         └───────────┘       └───────────┘
                  │                     │                     │
            document.yaml          audio.yaml           video.yaml
```

**Key moves:**

1. **Remove `creator` from expression entities** — No more `creator` property on `audio`, `recording`, or anywhere that extends `media` or `document`
2. **Attribution via relationships** — Use `references` with roles for all contributors
3. **Works are optional** — Create work entities when you have multiple expressions of the same creative content
4. **FRBR relationships via `references`** — Use `expression_of`, `manifestation_of`, `item_of` roles
5. **Observable vs inferred** — `posts` for account attribution (observable), `references(authored)` for person authorship (inferred or stated)

---

## Entity Hierarchy

### Primitives (Unchanged)

These remain as-is:

```yaml
# _primitives/work.yaml
id: work
properties:
  title: string (required)
  description: string
  original_creator: references: person  # ← Keep this
  created_date: string
```

```yaml
# _primitives/media.yaml
id: media
properties:
  title: string
  description: string
  url: string
  published_at: datetime
  duration_ms: integer
  thumbnail: references: image
  # NO creator property
```

```yaml
# _primitives/document.yaml
id: document
properties:
  content: string
  author: references: person  # ← REMOVE THIS
  title: string
  url: string
  published_at: datetime
  # NO author property after migration
```

### Expression Entities (Modified)

**Video, Audio, Recording:**

```yaml
# video.yaml
id: video
extends: media
# Inherits: title, description, url, published_at, duration_ms, thumbnail
# NO creator property
# Attribution via references relationship with roles
```

**Documents (Book, Post, Webpage):**

```yaml
# document.yaml (after migration)
id: document
properties:
  content: string
  # author: references: person  ← REMOVED
  title: string
  url: string
  published_at: datetime
```

```yaml
# book.yaml
extends: document
properties:
  isbn: string
  # Inherits content, title, url, published_at
  # NO author property
  # Use references(authored) for authorship
```

### Relationship-Based Attribution

**Old way (property-based):**
```yaml
# audio.yaml (current)
properties:
  creator: references: person
```

**New way (relationship-based):**
```yaml
# No creator property in entity
# Instead, use references relationship:
# person --references(authored)--> document
# person --references(composed)--> audio (music)
# person --references(narrator)--> audio (audiobook)
# person --references(director)--> video
# person --references(actor)--> video
```

**Observable attribution (social media):**
```yaml
# Use posts relationship:
# account --posts--> video
# account --posts--> post
# account --posts--> photo

# Then link person to account:
# person --claims--> account
```

---

## Relationship Types

### FRBR Core Relationships

These already exist in `references.yaml` (lines 103-143). No changes needed.

| Role | Direction | Example |
|------|-----------|---------|
| `expression_of` | Expression → Work | English Hamlet text → "Hamlet" work |
| `manifestation_of` | Manifestation → Expression | Kindle edition → English text |
| `item_of` | Item → Manifestation | My copy → First edition hardcover |
| `translation_of` | Expression → Expression | German text → English text |
| `adaptation_of` | Work → Work | LOTR film → LOTR novel |
| `performance_of` | Expression → Expression | Live recording → Sheet music |
| `variant_of` | Expression → Expression | Logo PNG ↔ Logo SVG |

### When to Use Each

**expression_of:** When you have multiple formats/languages/interpretations of the same work
- Book text, audiobook, film, stage play of "Hamlet" all → work: "Hamlet"
- Original score, various performances of Trout Quintet → work: "Trout Quintet"

**manifestation_of:** When you have different editions/publications
- 2003 Penguin paperback → English text expression
- Kindle edition → English text expression
- First edition hardcover → English text expression

**item_of:** When tracking specific copies
- My signed copy → First edition hardcover manifestation
- Library copy #3 → 2003 Penguin paperback manifestation

**translation_of:** Cross-language expressions
- German Hamlet → English Hamlet (both expressions of "Hamlet" work)

**adaptation_of:** Derivative works
- "West Side Story" work → "Romeo and Juliet" work
- "The Lord of the Rings" film work → "The Lord of the Rings" novel work

**performance_of:** Performed arts
- Boston Symphony 1997 recording → Schubert's original score
- Live jazz improvisation → Jazz standard (work)

---

## Role Modeling

### Contributor Roles by Level

**Work-level roles (original creation):**
- `author` → person --references(authored)--> work
- `composer` → person --references(composed)--> work
- `original_creator` → stored as property on work entity

**Expression-level roles (realization):**
- `translator` → person --references(translator)--> expression
- `narrator` → person --references(narrator)--> expression (audiobook)
- `performer` → person --references(performer)--> expression (music)
- `director` → person --references(director)--> expression (film)
- `actor` → person --references(actor)--> expression (film)
- `editor` → person --references(editor)--> expression

**Manifestation-level roles (publication):**
- `publisher` → organization --references(publisher)--> manifestation
- `producer` → person/org --references(producer)--> manifestation

**Item-level roles (ownership):**
- `owned_by` → person --references(owned_by)--> item

### Multi-Contributor Works

FRBR handles multi-contributor works naturally through multiple relationships:

**Example: Film**
```
Work: "Inception"
  ├─ person:Christopher_Nolan --references(authored)--> work:Inception (screenplay)
  └─ person:Christopher_Nolan --references(director)--> expression:Inception_2010_film
  └─ person:Leonardo_DiCaprio --references(actor)--> expression:Inception_2010_film
  └─ person:Hans_Zimmer --references(composer)--> work:Inception_score
  └─ person:Wally_Pfister --references(cinematographer)--> expression:Inception_2010_film
```

**Example: Audiobook**
```
Work: "Harry Potter and the Philosopher's Stone"
  └─ person:JK_Rowling --references(authored)--> work:HP_PS

Expression: English text
  └─ document:HP_PS_text --references(expression_of)--> work:HP_PS

Expression: English audiobook
  └─ audio:HP_PS_audiobook --references(expression_of)--> work:HP_PS
  └─ person:Stephen_Fry --references(narrator)--> audio:HP_PS_audiobook
```

**Example: Translation**
```
Work: "Crime and Punishment"
  └─ person:Dostoevsky --references(authored)--> work:Crime_Punishment

Expression: Russian original
  └─ document:CP_russian --references(expression_of)--> work:Crime_Punishment

Expression: English translation (Pevear/Volokhonsky)
  └─ document:CP_english_PV --references(expression_of)--> work:Crime_Punishment
  └─ document:CP_english_PV --references(translation_of)--> document:CP_russian
  └─ person:Pevear --references(translator)--> document:CP_english_PV
  └─ person:Volokhonsky --references(translator)--> document:CP_english_PV
```

### Music: Composition vs Performance

Music is where FRBR shines. The composition (work) is separate from performances (expressions):

```
Work: "Trout Quintet" (Schubert's composition)
  └─ person:Schubert --references(composed)--> work:Trout_Quintet
  └─ created_date: "1819"

Expression: Original score (sheet music)
  └─ document:Trout_score --references(expression_of)--> work:Trout_Quintet

Expression: Boston Symphony 1997 performance
  └─ audio:Trout_Boston_1997 --references(expression_of)--> work:Trout_Quintet
  └─ audio:Trout_Boston_1997 --references(performance_of)--> document:Trout_score
  └─ organization:Boston_Symphony --references(performer)--> audio:Trout_Boston_1997

Expression: Amadeus Quartet 1965 recording
  └─ audio:Trout_Amadeus_1965 --references(expression_of)--> work:Trout_Quintet
  └─ organization:Amadeus_Quartet --references(performer)--> audio:Trout_Amadeus_1965
```

---

## Expression vs Work: When to Create Each

### Default: Expressions Only

**Most content doesn't need work entities.** A YouTube video, a blog post, a podcast episode — these are just expressions. Create them as-is.

```
# Just a video entity, no work
video: "How to Make Sourdough Bread"
  └─ account:BakingChannel --posts--> video
```

### Create Work When: Multiple Expressions Exist

**Trigger: You have 2+ expressions of the same creative content.**

**Example: Same story in different formats**
```
Work: "The Martian"
  └─ person:Andy_Weir --references(authored)--> work:The_Martian

Expressions:
  ├─ document:The_Martian_text (novel)
  ├─ audio:The_Martian_audiobook (narrated by R.C. Bray)
  └─ video:The_Martian_film (directed by Ridley Scott)
```

**Example: Same album on different platforms**
```
Work: "Abbey Road" (album)
  └─ organization:The_Beatles --references(performed)--> work:Abbey_Road

Expressions:
  ├─ audio:Abbey_Road_Spotify (lossless stream)
  ├─ audio:Abbey_Road_CD (1987 CD master)
  └─ audio:Abbey_Road_Vinyl (original 1969 pressing)
```

### Inference Strategy for Adapters

**When adapters fetch content, they create expressions by default.**

**If the adapter knows about multiple formats, create a work:**

```yaml
# YouTube adapter (current behavior - no work)
# Just creates video entity

# Audible adapter (future - if book exists)
# 1. Check: does work exist with same title/author?
# 2. If yes, link audio:audiobook --references(expression_of)--> work
# 3. If no, just create audio entity (maybe work gets created later)
```

**User-driven work creation:**

```
User: "Link this audiobook to this book"
System:
  1. Create work entity
  2. Link book --references(expression_of)--> work
  3. Link audiobook --references(expression_of)--> work
  4. Copy author to work.original_creator
```

### Work Discovery Heuristics

**Match on:**
- Title similarity (fuzzy match)
- Author/creator match
- ISBN → Wikidata → multiple formats
- Shared Wikidata ID (different formats of same thing)

**Don't force it.** If you can't confidently match, leave as orphaned expressions. Works get created when there's actual evidence of multiple expressions.

---

## Migration Path

### Phase 1: Remove Creator Properties (Breaking Change)

**Changes needed:**

1. **Remove `author` from document.yaml**
2. **Remove `creator` from audio.yaml** (line 4 comment "inherits creator")
3. **Remove `creator` from recording.yaml** (line 4 comment "inherits creator")
4. **Verify video.yaml** (already removed, just confirm)
5. **Keep `sender` on message.yaml** (different semantics)
6. **Keep `original_creator` on work.yaml**

**Migration for existing data:**

```sql
-- For documents (books, posts, webpages)
-- Convert author property → references(authored) relationship
INSERT INTO relationships (from_type, from_id, to_type, to_id, relationship_type, role)
SELECT 'person', author_id, 'document', id, 'references', 'authored'
FROM documents
WHERE author_id IS NOT NULL;

-- For audio (music, podcasts)
-- Convert creator property → references(composed) or references(performed)
-- This needs domain knowledge — music is composed, podcasts are performed
-- Default to performed for ambiguous cases
INSERT INTO relationships (from_type, from_id, to_type, to_id, relationship_type, role)
SELECT 'person', creator_id, 'audio', id, 'references', 'performed'
FROM audio
WHERE creator_id IS NOT NULL;

-- For recordings (voice memos, calls)
-- Keep as-is or convert to sender-like semantics
-- These are captured moments, not authored works
```

**Schema changes:**

```yaml
# document.yaml (after)
properties:
  content: string
  # author: references: person ← REMOVED
  title: string
  url: string
```

```yaml
# audio.yaml (after)
extends: media
# Inherits: id, title, description, url, published_at, duration_ms, thumbnail
# creator: removed ← NO MORE
properties:
  bitrate: integer
  transcript: string
```

```yaml
# recording.yaml (after)
extends: media
# creator: removed ← NO MORE
properties:
  call_participants:
    type: array
    items: references: person
```

### Phase 2: Update Adapters (Non-Breaking)

**Adapters that currently map to `author` or `creator` need to use typed references instead.**

**Before (YouTube, current - already correct):**
```yaml
# youtube already uses typed references
posted_by:
  account:
    id: .channel_id
  _rel:
    type: '"posts"'
    reverse: true
```

**Before (hypothetical book adapter):**
```yaml
mapping:
  author: .author  # ← OLD WAY (property)
```

**After:**
```yaml
mapping:
  # Create person + references relationship
  author_person:
    person:
      id: .author_id
      name: .author_name
    _rel:
      type: '"references"'
      role: '"authored"'
      reverse: true  # person --references(authored)--> book
```

**Adapters to update:**
- Any adapter mapping to `author` (book adapters like Hardcover, Goodreads)
- Any adapter mapping to `creator` (audio adapters, music adapters)
- Reddit adapter (for posts) — change `author` to typed reference
- Hackernews adapter (for posts) — change `author` to typed reference

### Phase 3: Work Creation (Opt-In, Non-Breaking)

**Add work creation capability:**

1. **Manual work creation** — User says "create work for these expressions"
2. **Adapter hints** — Some adapters (like Audible) know they're getting an expression of an existing work
3. **Matching heuristics** — Background job to find expressions with same title/author and suggest work creation
4. **Wikidata integration** — If multiple entities share a Wikidata ID, create work

**Implementation:**

```yaml
# New utility: work.create
POST /api/works
{
  "title": "The Martian",
  "description": "A science fiction novel",
  "original_creator_id": "person:andy_weir",
  "expression_ids": [
    "document:martian_text",
    "audio:martian_audiobook",
    "video:martian_film"
  ]
}

# Creates:
# 1. work entity
# 2. references(expression_of) from each expression to work
# 3. Copies original_creator to work
```

### Phase 4: Adapter Enhancements (Future)

**Adapters that can infer works:**

- **Audible adapter** — Check if book exists with same ISBN, link to same work
- **OpenLibrary adapter** — Can return multiple editions (manifestations) of same work
- **Musicbrainz adapter** — Understands recordings (expressions) of releases (works)
- **Wikidata adapter** — Can fetch "has edition or translation" relationships

---

## Adapter Changes

### Adapters to Modify

**Priority 1 (have creator/author mappings):**

| Adapter | Entity | Current Mapping | New Mapping |
|---------|--------|----------------|-------------|
| Hardcover | book | `author: .author` | Typed reference with `authored` role |
| Goodreads | book | `author: .author` | Typed reference with `authored` role |
| Reddit | post | `author: .author` | Typed reference with `authored` role |
| Hackernews | post | `author: .by` | Typed reference with `authored` role |
| (any music adapter) | audio | `creator: .artist` | Typed reference with `performed` or `composed` role |

**Priority 2 (already correct, verify):**

| Adapter | Entity | Current Mapping | Status |
|---------|--------|----------------|--------|
| YouTube | video | `posted_by` (account) | ✓ Correct (uses `posts` relationship) |
| iMessage | message | `sender` | ✓ Correct (different semantics) |
| WhatsApp | message | `sender` | ✓ Correct (different semantics) |

**Priority 3 (future adapters):**

| Adapter | Entity | Mapping Needed |
|---------|--------|----------------|
| Audible | audio | Typed reference for narrator; check for existing work |
| Spotify | audio | Typed reference for artist (performer); link to work if album exists |
| OpenLibrary | book | Create work + multiple manifestations (editions) |
| Musicbrainz | audio | Distinguish work (composition) from recording (performance) |

### Example: Hardcover Adapter Update

**Before:**
```yaml
# adapters/hardcover/readme.md
adapters:
  book:
    mapping:
      id: .id
      title: .title
      author: .author  # ← OLD WAY
      isbn: .isbn
      cover: .cover_url
```

**After:**
```yaml
adapters:
  book:
    mapping:
      id: .id
      title: .title
      isbn: .isbn
      cover: .cover_url
      
      # Create person entity + references(authored) relationship
      author_ref:
        person:
          id: .author_id
          name: .author_name
        _rel:
          type: '"references"'
          role: '"authored"'
          reverse: true  # person --references(authored)--> book
```

### Example: Future Audible Adapter

```yaml
# adapters/audible/readme.md
adapters:
  audio:
    mapping:
      id: .asin
      title: .title
      description: .summary
      duration_ms: .length_ms
      thumbnail: .cover_url
      
      # Narrator (expression-level contributor)
      narrator_ref:
        person:
          id: .narrator_id
          name: .narrator_name
        _rel:
          type: '"references"'
          role: '"narrator"'
          reverse: true  # person --references(narrator)--> audio
      
      # Try to link to existing work (if book exists)
      # This is an adapter utility that checks for matching ISBN
      work_link:
        ref: work
        value: .isbn  # Look up work by ISBN
        rel: expression_of
```

---

## Open Questions

### 1. Social Media Attribution: Account vs Person

**Context:** YouTube videos, Reddit posts, tweets — we observe accounts posting, not people directly.

**Current approach:**
- `account --posts--> video` (observable)
- `person --claims--> account` (inferred)

**Question:** Should social media expressions use `references(authored)` at all? Or is `posts` sufficient?

**Options:**

**A) Posts only (current for video)**
```
account --posts--> video
person --claims--> account
# No direct person → video relationship
```

**B) Posts + references**
```
account --posts--> video
person --claims--> account
person --references(authored)--> video  # Inferred from claims
```

**C) Context-dependent**
- Social media (YouTube, Reddit): Use `posts` only
- Traditional media (books, albums): Use `references(authored)` directly

**Recommendation:** **Option C**. Social media uses `posts` (observable attribution to account). Traditional published content uses `references(authored)` (stated authorship). This matches current video.yaml behavior.

---

### 2. When to Collapse FRBR Levels

**Context:** BIBFRAME collapsed Expression + Manifestation into "Instance". Should we?

**Current approach:** Keep all four levels available via `references` roles.

**Question:** Should we have:
- Separate `manifestation` entity type? (Currently no)
- Separate `item` entity type? (Currently no)

**Options:**

**A) Keep as relationships only (current)**
```yaml
# No manifestation entity type
# Just use references:
document --references(manifestation_of)--> document  # Edition X of text Y
```

**B) Add manifestation entity**
```yaml
# _primitives/manifestation.yaml
id: manifestation
properties:
  publisher: string
  published_year: integer
  isbn: string
  format: string  # paperback, hardcover, ebook
```

**C) Let expressions be manifestations**
```yaml
# book.yaml already has publisher, format, isbn
# These are manifestation-level properties
# Just use the book entity as manifestation
```

**Recommendation:** **Option A**. No separate manifestation entity. Use the existing entity types (book, audio, video) and let them represent expressions or manifestations depending on granularity. If you need to distinguish editions, create separate book entities and link them with `references(variant_of)` or `references(manifestation_of)`.

**Rationale:** Entities should represent observable things. "Manifestation" is a conceptual level, not a thing you interact with. The 2003 Penguin paperback *is* a book entity. The Kindle edition *is* a book entity. They can reference each other via `variant_of`.

---

### 3. Post as Work or Expression?

**Context:** Is a blog post a work or an expression?

**Question:** 
- A blog post is text (expression)
- But it's also the original work (no underlying abstraction)
- Should every post implicitly have a work?

**Options:**

**A) Posts are works** (no explicit work entity unless cross-posted)
```
# A Reddit post is a work
post:reddit_12345 (work-level entity, no explicit work)
```

**B) Posts are expressions of implicit works**
```
# Every post has an implicit work
post:reddit_12345 --references(expression_of)--> work:reddit_12345_work
```

**C) Posts are expressions, work created when cross-posted**
```
# A Reddit post is just an expression
post:reddit_12345

# If cross-posted to Twitter:
work:idea_X
  ├─ post:reddit_12345 --references(expression_of)--> work:idea_X
  └─ post:twitter_67890 --references(expression_of)--> work:idea_X
```

**Recommendation:** **Option C**. Posts are expressions by default. Create a work entity only when the same content is posted in multiple places (cross-posted, reposted, syndicated).

**Why:** FRBR says "Works appear when you actually have multiple representations." A single Reddit post is just an expression. If it's cross-posted to Twitter, HN, and LinkedIn — *then* create a work to group them.

---

### 4. Remixes, Covers, Samples: Derivative Works

**Context:** A cover song, a remix, a sample — are these expressions or works?

**FRBR says:**
- **Same work, different expression:** Boston Symphony playing Schubert (performance)
- **Derivative work:** Jazz improvisation on a standard (new work, uses references(derived_from))

**Question:** How to model:
- Cover song (someone else performing the same song)
- Remix (someone altering a recording)
- Sample (someone using a piece of a recording)

**Options:**

**A) Covers are expressions, remixes are works**
```
Work: "Hallelujah" (Leonard Cohen)
  ├─ audio:cohen_original --references(expression_of)--> work:Hallelujah
  └─ audio:buckley_cover --references(expression_of)--> work:Hallelujah
      └─ person:Jeff_Buckley --references(performer)--> audio:buckley_cover

Work: "Hallelujah (Remix)" (DJ XYZ)
  └─ audio:xyz_remix --references(expression_of)--> work:Hallelujah_Remix
  └─ work:Hallelujah_Remix --references(derived_from)--> work:Hallelujah
```

**B) Everything is a new work**
```
# Even covers are new works
Work: "Hallelujah" (Cohen original)
Work: "Hallelujah" (Buckley version) --references(adaptation_of)--> Cohen work
```

**Recommendation:** **Option A**. 
- **Cover = expression** (same composition, different performance)
- **Remix = new work** (different creative product, derived)
- **Sample = references** (work --references(samples)--> work)

Add `samples` role to `references.yaml`:
```yaml
samples:
  name: Samples
  inverse_name: Sampled by
  description: Uses a portion of another work
```

---

### 5. Author vs Authored: Property vs Relationship

**Context:** `work` entity has `original_creator` property. Should it?

**Current:**
```yaml
# work.yaml
properties:
  original_creator: references: person
```

**Question:** Should this be a property or a relationship?

**Options:**

**A) Keep as property (current)**
```yaml
work:
  original_creator: references: person
```

**B) Remove property, use relationship**
```yaml
# No original_creator property
# Instead:
person --references(authored)--> work
```

**C) Both (redundant but convenient)**
```yaml
# Property for easy access
original_creator: references: person

# Relationship for graph traversal
person --references(authored)--> work
```

**Recommendation:** **Option B**. Remove `original_creator` property. Use `references(authored)` for all authorship.

**Why:** 
- Consistency — all attribution is via relationships
- Handles multi-author works naturally (multiple references relationships)
- No redundancy between property and relationship
- Graph traversal works the same for all entities

**Migration:**
```sql
-- Convert original_creator property → references(authored) relationship
INSERT INTO relationships (from_type, from_id, to_type, to_id, relationship_type, role)
SELECT 'person', original_creator_id, 'work', id, 'references', 'authored'
FROM works
WHERE original_creator_id IS NOT NULL;

-- Drop column
ALTER TABLE works DROP COLUMN original_creator_id;
```

---

### 6. Discovery UI: How to Show Works vs Expressions

**Context:** If a user searches for "Hamlet", do they see:
- The work "Hamlet"?
- All expressions (30+ books, films, audiobooks)?
- Both?

**Question:** What's the default search/browse behavior?

**Options:**

**A) Search returns expressions (current)**
```
Search: "Hamlet"
Results:
  - Hamlet (Penguin Classics)
  - Hamlet (Folger Shakespeare)
  - Hamlet (1996 film)
  - Hamlet (audiobook)
```

**B) Search returns works, click to see expressions**
```
Search: "Hamlet"
Results:
  - Hamlet (work) — 30 expressions
    [Click to expand]
```

**C) Grouped results**
```
Search: "Hamlet"
Results:
  Work: "Hamlet" by William Shakespeare
    Expressions:
      - Hamlet (Penguin Classics) — book
      - Hamlet (1996 film) — video
      - Hamlet (audiobook, Simon Russell Beale) — audio
```

**Recommendation:** **Option C** (grouped), with fallback to **Option A** (flat) for expressions without works.

**UI behavior:**
- Search returns entities (expressions)
- If entity has `expression_of` relationship, show work badge/grouping
- Option to "show all expressions of this work"
- Option to "collapse to works" in search results

---

### 7. ISBN, ASIN, UPC: Which Level?

**Context:** ISBNs identify editions (manifestations). ASINs identify products (manifestations). UPCs identify physical products.

**Current:** `book.yaml` has `isbn` property.

**Question:** Is this correct, or should ISBN be on manifestation?

**FRBR says:** ISBN is manifestation-level.

**But:** We collapsed manifestation into expression (no separate entity).

**Recommendation:** Keep ISBN on book entity. The book entity represents both expression and manifestation (BIBFRAME approach). If you need to distinguish editions with different ISBNs, create separate book entities.

**Example:**
```
Work: "Harry Potter and the Philosopher's Stone"

Expressions/Manifestations (combined):
  - book:HP_UK_1997 (ISBN: 0-7475-3269-9, UK first edition)
  - book:HP_US_1998 (ISBN: 0-590-35340-3, US edition, titled "Sorcerer's Stone")
  - book:HP_UK_2014 (ISBN: 978-1408855652, UK illustrated edition)

All link via:
  book --references(expression_of)--> work:HP_PS
  book:HP_US_1998 --references(translation_of)--> book:HP_UK_1997
```

---

## Summary

### Key Decisions

1. **Remove `creator`/`author` properties** from all expression entities (document, audio, video, recording)
2. **Keep `original_creator` on work** (for now — consider removing in future)
3. **Use `references` relationships with roles** for all attribution
4. **FRBR is opt-in** — works created only when multiple expressions exist
5. **Social media uses `posts`** (account attribution), traditional media uses `references(authored)` (person attribution)
6. **Covers are expressions, remixes are works**
7. **ISBN stays on book entity** (collapsed manifestation)
8. **Discovery shows grouped results** when work exists

### Migration Sequence

1. **Phase 1:** Remove creator properties (breaking change, needs data migration)
2. **Phase 2:** Update adapters to use typed references (non-breaking, adapter-by-adapter)
3. **Phase 3:** Add work creation utilities (non-breaking, opt-in)
4. **Phase 4:** Enhance adapters with work inference (non-breaking, opportunistic)

### Next Steps

1. **Review this spec** — Joe weighs in on open questions
2. **Prototype work creation** — Test creating work + linking expressions
3. **Migrate one adapter** — Start with Hardcover (book adapter)
4. **Test attribution queries** — "Show me everything by person X"
5. **Design discovery UI** — Grouped results with work/expression hierarchy

---

## Appendix: FRBR Resources

- [IFLA FRBR Final Report (2009)](https://www.ifla.org/wp-content/uploads/2019/05/assets/cataloguing/frbr/frbr_2008.pdf)
- [BIBFRAME 2.0 Model](https://www.loc.gov/bibframe/docs/bibframe2-model.html)
- [Schema.org CreativeWork](https://schema.org/CreativeWork)
- [Wikidata FRBR properties](https://www.wikidata.org/wiki/Wikidata:WikiProject_Periodicals/FRBR)
