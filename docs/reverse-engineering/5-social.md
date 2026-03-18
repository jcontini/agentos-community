# Reverse Engineering — Social Network Patterns

How to model people, relationships, and social data across platforms like
Goodreads, Twitter/X, MySpace, LinkedIn, Instagram, etc.

This is Layer 5 of the reverse-engineering docs:

- **Layer 1: Transport** — [1-transport.md](1-transport.md) — getting a response at all
- **Layer 2: Discovery** — [2-discovery.md](2-discovery.md) — finding structured data in bundles
- **Layer 3: Auth & Runtime** — [3-auth.md](3-auth.md) — credentials, sessions, rotating config
- **Layer 4: Content** — [4-content.md](4-content.md) — extracting data from HTML when there is no API
- **Layer 5: Social Networks** (this file) — modeling people, relationships, and social graphs
- **Layer 6: Desktop Apps** — [6-desktop-apps.md](6-desktop-apps.md) — macOS, Electron, local state, unofficial APIs

---

## Core Principle: People First, Accounts Second

Every social platform has users. But the same person exists across many platforms.
The graph should model this in two layers:

| Entity | What it represents | Cross-platform? |
|---|---|---|
| **person** | A real human being | Yes — mergeable across platforms |
| **account** | Their profile on one platform | No — platform-specific |

A person *has* accounts. An account *belongs to* a person.

```yaml
adapters:
  person:
    id: .user_id
    name: .name
    image: .photo_url
    location: .location
    data.gender: .gender
    data.age: .age
    data.birthday: .birthday
    data.website: .website

    has_account:
      account:
        id: .user_id
        name: .name
        handle: .handle
        url: .profile_url
        image: .photo_url
```

**Why this matters:** When you later build Twitter and find the same person
(by name, website, or explicit cross-link), you can merge the person entities
while keeping both accounts distinct. The person is the anchor.

---

## Social Relationship Types

Every social network has some subset of these relationship patterns:

### Symmetric (mutual)

Both parties agree. The relationship is bidirectional.

| Relationship | Examples |
|---|---|
| **friends** | Facebook, Goodreads, MySpace |

Operation pattern: `list_friends(user_id)` → `person[]`

### Asymmetric (directed)

One party follows, the other may or may not follow back.

| Relationship | Examples |
|---|---|
| **following** | Twitter, Instagram, Goodreads |
| **followers** | Twitter, Instagram, Goodreads |

Operation pattern: two separate operations with different directions.
```yaml
list_following:
  description: People this user follows
  returns: person[]

list_followers:
  description: People following this user
  returns: person[]
```

### Group membership

User belongs to a group/community.

| Relationship | Examples |
|---|---|
| **member_of** | Goodreads groups, Facebook groups, Reddit subreddits, Discord servers |

```yaml
list_groups:
  returns: group[]
```

---

## Profile Depth: Light vs Rich

Social operations return people at two levels of depth:

### Light (from list operations)

When you scrape a friends list or followers page, you get limited data per person:

```python
{
    "user_id": "27117656",
    "name": "Kirill So",
    "photo_url": "https://...",
    "location": "Singapore",
    "books_count": 414,
    "friends_count": 138,
}
```

This is what `list_friends`, `list_following`, `list_followers` return.
Enough to create the person entity and the relationship edge.

### Rich (from profile scrape)

When you scrape an individual profile page, you get the full picture:

```python
{
    "user_id": "27117656",
    "name": "Kirill So",
    "handle": "kirso",
    "photo_url": "https://...",
    "gender": "Male",
    "age": 37,
    "birthday": "April 15, 1988",
    "location": "Singapore, Singapore",
    "website": "https://www.kirillso.com",
    "about": "...",
    "interests": "...",
    "joined_date": "December 2013",
    "ratings_count": 159,
    "avg_rating": "3.82",
    "friends_count": 138,
    "favorite_books": [...],
    "currently_reading": [...],
    "favorite_genres": [...],
}
```

This is what `get_person(user_id)` returns.

**Pattern:** Always provide both. The light operations populate the graph with
stubs. The rich operation fills them in when you need the detail. The adapter
handles both — missing fields are just `null`.

---

## Authors Are People Too

On platforms with content creators (Goodreads authors, Twitter blue-checks,
YouTube channels), the creators are people with special roles. Model them as:

1. **person** entity (they're a human being)
2. **author/creator** entity (their creative identity)
3. **account** entity (their platform presence)

On Goodreads, an author appears in multiple contexts:

| Context | How we encounter them |
|---|---|
| Book's `written_by` relationship | author entity with ID and URL |
| `list_following` results | person entity (they follow authors) |
| Quote attribution | author entity |
| Author profile page | full author entity with books |

The key insight: extract real author IDs everywhere, not just name strings.
When a book list shows "Christie, Agatha" as a link to `/author/show/123715`,
capture the ID so the graph can connect the book → author → their other books.

```python
author_el = row.select_one("td.field.author a")
if author_el:
    href = author_el.get("href", "")
    m = re.search(r"/author/show/(\d+)", href)
    if m:
        author_id = m.group(1)
        author_url = _abs_url(href)
```

Also fix name ordering — many platforms store names as "LastName, FirstName"
in table views:

```python
def _flip_name(name: str) -> str:
    if "," in name:
        parts = [p.strip() for p in name.split(",", 1)]
        if len(parts) == 2 and parts[1]:
            return f"{parts[1]} {parts[0]}"
    return name
```

---

## Content People Create

Social platforms aren't just about connections — people create content.
Each platform has its own content types that should map to entities:

| Platform | Content types | Entity mapping |
|---|---|---|
| Goodreads | Books read, reviews, ratings, quotes | book, review, quote |
| Twitter | Tweets, retweets, likes | post, engagement |
| MySpace | Music, blog posts, comments | track, post, comment |
| Instagram | Photos, stories, reels | media, story |
| LinkedIn | Posts, articles, endorsements | post, article |

The person's *relationship* to content matters:

```yaml
# Things a person created
person → wrote → review
person → posted → post

# Things a person engaged with
person → rated → book (with rating value)
person → liked → quote
person → saved → book (to shelf)

# Things attributed to a person
quote → attributed_to → author
book → written_by → author
```

---

## Profile Page Parsing Patterns

Social profile pages follow remarkably similar structures across platforms.
Common patterns:

### Info box / details section

Most profiles have a key-value info section:

```python
titles = soup.select(".infoBoxRowTitle")
items = soup.select(".infoBoxRowItem")
info = {}
for t, v in zip(titles, items):
    label = clean(t.get_text()).lower()
    value = clean(v.get_text())
    info[label] = value
```

### Stats bar

Ratings, posts, followers — usually near the top:

```python
stats_text = clean(stats_el.get_text())
ratings = re.search(r"([\d,]+)\s+ratings?", stats_text)
avg = re.search(r"\(([\d.]+)\s+avg\)", stats_text)
```

### Section headers → content blocks

Profile pages have named sections (favorite books, currently reading, groups).
The header-to-content relationship varies by platform:

```python
# Pattern 1: Header is inside a container, content is a sibling div
for hdr in soup.select("h2.brownBackground"):
    parent_box = hdr.find_parent("div", class_="bigBox")
    body = parent_box.select_one(".bigBoxBody") if parent_box else None

# Pattern 2: Header IS the container, content follows
for hdr in soup.select(".sectionHeader"):
    body = hdr.find_next_sibling()

# Pattern 3: Header + content share a parent
for section in soup.select(".profileSection"):
    title = section.select_one("h3")
    content = section.select_one(".sectionContent")
```

Always check the actual DOM structure — don't assume.

---

## Pagination for Social Lists

Social lists (friends, followers, following) almost always paginate.
Key patterns from Goodreads that will apply elsewhere:

### Auto-pagination with `page=0`

```python
def list_friends(user_id, page=0, ...):
    """page=0 means fetch all pages automatically."""
    if page > 0:
        return _fetch_single_page(page)

    all_items = []
    seen = set()
    for p in range(1, MAX_PAGES + 1):
        items = _fetch_single_page(p)
        new = [i for i in items if i["user_id"] not in seen]
        all_items.extend(new)
        seen.update(i["user_id"] for i in new)
        if not _has_next(html_text):
            break
    return all_items
```

### Next-page detection

```python
def _has_next(html_text: str) -> bool:
    return 'class="next_page"' in html_text or "rel=\"next\"" in html_text
```

### Safety limits

Always cap pagination to prevent infinite loops:

```python
MAX_PAGES = 50
```

---

## Cross-Platform Identity Signals

When building skills for multiple social networks, look for identity signals
that help merge person entities across platforms:

| Signal | Reliability | Example |
|---|---|---|
| Explicit cross-link | High | Website URL in bio pointing to another profile |
| Same handle | Medium | `@jcontini` on both Twitter and Goodreads |
| Same name + location | Low | "Joe Contini, Austin TX" |
| Same profile photo | Medium | Image similarity matching |
| Email (if available) | High | Unique identifier |

For now, just capture everything. The `website` field on a person's profile
is particularly valuable — it often links to a personal site that aggregates
all their social profiles.

---

## Checklist for a New Social Network Skill

When building a skill for a new social platform:

1. **Identify the entity types** — what do people create, consume, and engage with?
2. **Map relationships** — friends? followers? groups? what content do they produce?
3. **Model as person → account** — not just accounts
4. **Light + rich profiles** — list operations for stubs, get_person for detail
5. **Extract real IDs everywhere** — not just name strings; follow links for IDs
6. **Capture cross-platform signals** — website, handle, email
7. **Auto-paginate social lists** — friends, followers, etc. are always paginated
8. **Handle name formatting** — "LastName, FirstName" flipping, Unicode, etc.
9. **Look for section-based profile data** — favorite X, currently Y, groups, etc.
10. **Test with a real profile** — verify data richness against what you see in the browser

---

## Real-World Examples

| Skill | Social patterns used | Reference |
|---|---|---|
| `skills/goodreads/` | person → account, friends, following/followers, groups, quotes, authors as people, favorite books, currently reading, profile scraping | `web_scraper.py` |
| Future: `skills/myspace/` | person → account, friends, followers, music, blog posts | — |
| Future: `skills/twitter/` | person → account, following/followers, tweets, likes, retweets | — |
