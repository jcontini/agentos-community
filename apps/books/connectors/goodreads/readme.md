---
id: goodreads
name: Goodreads
description: Import your reading library from Goodreads CSV export
icon: icon.png
website: https://goodreads.com

apps:
  - books

# No auth needed - CSV file import only
auth: null
---

# Goodreads Connector

Import your reading library from Goodreads via CSV export.

## Why CSV?

Goodreads discontinued their public API around 2020. CSV export is the only reliable way to get your data out.

## How to Export from Goodreads

1. Go to [goodreads.com](https://goodreads.com)
2. Click "My Books"
3. Click "Import and export" (left sidebar)
4. Click "Export Library"
5. Wait for export to complete, then download the CSV

## Import Command

```
Books(action: "import", connector: "goodreads", path: "~/Downloads/goodreads_library_export.csv")
```

## Field Mapping

| Goodreads Column | Books Field | Notes |
|------------------|-------------|-------|
| Book Id | goodreads_id | For dedup |
| Title | title | |
| Author | authors[0] | |
| Additional Authors | authors[1..] | |
| ISBN | isbn | Stripped of `="..."` wrapper |
| ISBN13 | isbn13 | Stripped of `="..."` wrapper |
| My Rating | rating | 0 = no rating → null |
| Exclusive Shelf | status | Mapped (see below) |
| Bookshelves | shelves | Comma-separated |
| My Review | review | |
| Private Notes | notes | |
| Date Read | date_finished | Only most recent |
| Date Added | date_added | |
| Number of Pages | page_count | |
| Publisher | publisher | |
| Year Published | published_year | |

## Status Mapping

| Goodreads Shelf | Books Status |
|-----------------|--------------|
| to-read | want_to_read |
| currently-reading | reading |
| read | read |

## Known Limitations

- **No start dates**: Goodreads CSV doesn't include when you started a book
- **Single finish date**: Only the most recent read date is exported
- **No re-read tracking**: Multiple reads of same book not captured
- **No progress**: Current page/percentage not available

These are Goodreads export limitations, not AgentOS limitations.
