#!/usr/bin/env python3
"""
Authenticated Goodreads web scraping — friends, books, shelves, reviews, search people.

Uses http.client + lxml for HTML parsing. Requires cookies via connection: web; AgentOS provides them.
Separate from public_graph.py which handles public GraphQL/Apollo data.
"""

import re
from typing import Any
from urllib.parse import quote_plus

from agentos import get_cookies, http, molt, connection, provides, returns, timeout, email_lookup, parse_date, parse_int
from lxml import html as lhtml
from lxml.html import HtmlElement

BASE = "https://www.goodreads.com"
MAX_PAGES = 20
PER_PAGE_FRIENDS = 30
PER_PAGE_BOOKS = 25

# Goodreads is behind CloudFront — all requests need WAF headers.
_H = http.headers(waf="cf", accept="html")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse(html_text: str) -> HtmlElement:
    """Parse HTML string into an lxml document."""
    return lhtml.fromstring(html_text)


def _first(el: HtmlElement, selector: str) -> HtmlElement | None:
    """CSS select returning first match or None."""
    matches = el.cssselect(selector)
    return matches[0] if matches else None


def _text(el: HtmlElement | None) -> str:
    """Extract stripped text from an element, or empty string if None."""
    if el is None:
        return ""
    return (el.text_content() or "").strip()


def _fetch(client, url: str) -> tuple[int, str]:
    resp = client.get(url, **_H)
    return resp["status"], resp["body"]


def _has_next(html_text: str) -> bool:
    """Check if there's a 'next' pagination link."""
    doc = _parse(html_text)
    return bool(doc.cssselect('.next_page, [rel="next"]'))


def _require_login(html_text: str) -> None:
    doc = _parse(html_text[:4000])
    title_el = _first(doc, "title")
    if title_el:
        title_text = _text(title_el)
        if "Sign Up" in title_text or "Sign in" in title_text:
            raise RuntimeError("Page requires login — cookies invalid or expired")



def _abs_url(path: str | None) -> str | None:
    if not path:
        return None
    return f"{BASE}{path}" if path.startswith("/") else path



def _flip_name(name: str) -> str:
    """Convert 'LastName, FirstName' to 'FirstName LastName'."""
    if "," in name:
        parts = [p.strip() for p in name.split(",", 1)]
        if len(parts) == 2 and parts[1]:
            return f"{parts[1]} {parts[0]}"
    return name


def _field_value(row: Any, field_class: str) -> str | None:
    """Extract cleaned text from a td.field.<class> .value cell."""
    td = _first(row, f"td.field.{field_class}")
    if not td:
        return None
    val_el = _first(td, ".value")
    text = molt((val_el or td).text_content())
    if text and text.lower() in ("not set", "unknown"):
        return None
    return text



def _p(d: dict, key: str, default: Any = None) -> Any:
    """Get from params sub-dict or top-level."""
    p = (d.get("params") or d) if isinstance(d, dict) else {}
    return p.get(key, default) if isinstance(p, dict) else default


def _require_cookies(cookie_header: str | None, params: dict | None, op: str) -> str:
    cookie_header = cookie_header or get_cookies(params)
    if not cookie_header:
        raise ValueError(
            f"{op} requires Goodreads session cookies. "
            "Sign in at goodreads.com; AgentOS provides cookies via the web connection."
        )
    return cookie_header


# ---------------------------------------------------------------------------
# Session check — called by account.check with params: true
# ---------------------------------------------------------------------------


@returns({"authenticated": "boolean", "identifier": "string", "display": "string"})
@connection("web")
@timeout(15)
def check_session(**params) -> dict[str, Any]:
    """Verify Goodreads session and identify the logged-in user.

    Fetches the Goodreads homepage with cookies and extracts the logged-in
    user's ID and name from the navigation HTML.
    """
    cookie_header = get_cookies(params)
    if not cookie_header:
        return {"authenticated": False, "error": "no cookies"}

    resp = http.get(BASE, cookies=cookie_header, **_H)
    if resp["status"] != 200:
        return {"authenticated": False, "statusCode": resp["status"]}

    body = resp["body"]

    # Redirect to sign-in means cookies are invalid
    if "/user/sign_in" in str(resp["url"]):
        return {"authenticated": False, "redirect": str(resp["url"])}

    # Extract user ID from profile link: /user/show/12345-name
    user_id_match = re.search(r'/user/show/(\d+)', body)
    # Extract display name from URL slug: /user/show/12345-first-last
    name = ""
    slug_match = re.search(r'/user/show/\d+-([^"&?/]+)', body)
    if slug_match:
        name = slug_match.group(1).replace("-", " ").strip().title()

    user_id = user_id_match.group(1) if user_id_match else ""

    if user_id:
        return {
            "authenticated": True,
            "domain": "goodreads.com",
            "identifier": user_id,
            "display": name,
        }

    return {"authenticated": False}


# ---------------------------------------------------------------------------
# Entry points (called by AgentOS with auto-dispatch kwargs)
# ---------------------------------------------------------------------------


@returns("person")
@connection("web")
@timeout(15)
def run_get_person(*, user_id: str = "", **params) -> dict[str, Any]:
    """Get a rich person profile from Goodreads — demographics, stats, favorite books, genres, currently reading

        Args:
            user_id: User ID (e.g., '27117656')
        """
    return _get_person(user_id=str(user_id), params=params)


@returns("person[]")
@connection("web")
@timeout(15)
def run_search_people(*, query: str = "", limit: int = 10, **params) -> list[dict[str, Any]]:
    """Search for Goodreads users by name

        Args:
            query: Name to search
            limit: Max results (default 10)
        """
    return _search_people(query=query, limit=int(limit), params=params)


def _resolve_user_id(user_id: str, params: dict) -> str:
    """Resolve user_id: explicit param → auth.identifier from check_session."""
    uid = str(user_id).strip() if user_id else ""
    if not uid:
        uid = (params.get("auth") or {}).get("identifier", "")
    if not uid:
        raise ValueError("user_id required — provide it or ensure check_session has run")
    return uid


@returns("person[]")
@connection("web")
@timeout(60)
def run_list_friends(*, user_id: str = "", page: int = 0, **params) -> list[dict[str, Any]]:
    """List a user's friends as people with linked Goodreads accounts

        Args:
            user_id: User ID
            page: Page number (0 = all pages, 30 per page)
        """
    return _list_friends(user_id=_resolve_user_id(user_id, params), page=int(page), params=params)


@returns("book[]")
@connection("web")
@timeout(60)
def run_list_books(*, user_id: str = "", shelf: str = "all", sort: str = "date_added", page: int = 0, **params) -> list[dict[str, Any]]:
    """List a user's books organized by shelf (requires Goodreads session cookies)

        Args:
            user_id: User ID
            shelf: Shelf: all, read, currently-reading, to-read, did-not-finish (default: all)
            sort: Sort by: date_added, rating, title, author
            page: Page number (0 = all pages, 25 per page)
        """
    return _list_books(user_id=_resolve_user_id(user_id, params), shelf=str(shelf), sort=str(sort), page=int(page), params=params)


@returns("review[]")
@connection("web")
@timeout(60)
def run_list_reviews(*, user_id: str = "", sort: str = "date", page: int = 0, **params) -> list[dict[str, Any]]:
    """List your book reviews with ratings and dates (requires Goodreads session cookies)

        Args:
            user_id: User ID
            sort: Sort by: date, rating, title
            page: Page number (0 = all pages, 25 per page)
        """
    return _list_reviews(user_id=_resolve_user_id(user_id, params), sort=str(sort), page=int(page), params=params)


@returns("shelf[]")
@connection("web")
@timeout(15)
def run_list_shelves(*, user_id: str = "", **params) -> list[dict[str, Any]]:
    """List a user's bookshelves including default shelves (read, currently-reading, want-to-read)

        Args:
            user_id: User ID
        """
    return _list_shelves(user_id=_resolve_user_id(user_id, params), params=params)


@returns("book[]")
@connection("web")
@timeout(60)
def run_list_shelf_books(*, user_id: str = "", shelf_name: str = "", page: int = 0, **params) -> list[dict[str, Any]]:
    """List books on a specific user shelf (requires Goodreads session cookies)

        Args:
            user_id: User ID
            shelf_name: Shelf name (e.g., 'read', 'currently-reading', 'to-read')
            page: Page number (0 = all pages, 25 per page)
        """
    return _list_shelf_books(user_id=_resolve_user_id(user_id, params), shelf_name=str(shelf_name), page=int(page), params=params)


@returns("person[]")
@provides(email_lookup)
@connection("web")
@timeout(15)
def run_resolve_email(*, email: str = "", **params) -> list[dict[str, Any]]:
    """Look up a person on Goodreads by email address

        Args:
            email: Email address to search for
        """
    return _resolve_email(email=str(email), params=params)


@returns("group[]")
@connection("web")
def run_list_groups(**params) -> list[dict[str, Any]]:
    """List the authenticated user's Goodreads groups"""
    return _list_groups(params=params)


@returns("person[]")
@connection("web")
@timeout(15)
def run_list_following(*, user_id: str = "", **params) -> list[dict[str, Any]]:
    """List people (users and authors) a user is following

        Args:
            user_id: User ID
        """
    return _list_following(user_id=_resolve_user_id(user_id, params), params=params)


@returns("person[]")
@connection("web")
@timeout(15)
def run_list_followers(*, user_id: str = "", **params) -> list[dict[str, Any]]:
    """List people following a user

        Args:
            user_id: User ID
        """
    return _list_followers(user_id=_resolve_user_id(user_id, params), params=params)


@returns("quote[]")
@connection("web")
@timeout(15)
def run_list_quotes(*, user_id: str = "", **params) -> list[dict[str, Any]]:
    """List a user's liked/saved quotes with author attribution

        Args:
            user_id: User ID
        """
    return _list_quotes(user_id=_resolve_user_id(user_id, params), params=params)


# ---------------------------------------------------------------------------
# Person (rich profile scrape)
# ---------------------------------------------------------------------------


def _get_person(
    user_id: str,
    cookie_header: str | None = None,
    *,
    params: dict | None = None,
) -> dict[str, Any]:
    """Scrape a full Goodreads profile page and return rich person data."""
    cookie_header = cookie_header or get_cookies(params)
    url = f"{BASE}/user/show/{user_id}"
    resp = http.get(url, cookies=cookie_header, **_H)
    status, html_text = resp["status"], resp["body"]
    if status != 200:
        raise RuntimeError(f"Profile page returned {status}")

    doc = _parse(html_text)

    name_el = _first(doc,"h1.userProfileName, .userProfileName")
    name = molt(name_el.text_content()) if name_el else None
    if name:
        name = re.sub(r"\s*\(edit profile\)", "", name).strip()

    img_el = _first(doc,".leftAlignedProfilePicture img, .profilePicture img, .userProfileImage")
    photo_url = img_el.get("src") if img_el else None

    # Username from title: "Joe Contini (jcontini) - Austin, TX (273 books)"
    title_el = _first(doc,"title")
    title_text = molt(title_el.text_content()) if title_el else ""
    handle = None
    hm = re.search(r"\((\w+)\)", title_text or "")
    if hm and not hm.group(1).isdigit():
        handle = hm.group(1)

    # Parse info box rows
    info: dict[str, str] = {}
    for t, v in zip(doc.cssselect(".infoBoxRowTitle"), doc.cssselect(".infoBoxRowItem")):
        label = (molt(t.text_content()) or "").lower()
        value = molt(v.text_content()) or ""
        info[label] = value

    # Details: "Age 37, Male, Singapore, Singapore"
    details = info.get("details", "")
    age = None
    gender = None
    location = None
    age_m = re.search(r"Age\s+(\d+)", details)
    if age_m:
        age = int(age_m.group(1))
    gender_m = re.search(r"(Male|Female|Non-binary|Custom)", details, re.I)
    if gender_m:
        gender = gender_m.group(1)
    # Location: everything after gender comma, or the whole string minus age/gender
    loc_m = re.search(r"(?:Male|Female|Non-binary|Custom),\s*(.+)", details, re.I)
    if loc_m:
        location = loc_m.group(1).strip()
        # Remove distance like "(0 mi)"
        location = re.sub(r"\s*\(\d+\s*mi\)", "", location).strip()
    elif not age_m and not gender_m and details:
        location = details

    birthday = parse_date(info.get("birthday"))
    website = info.get("website")
    interests = info.get("interests")
    about = info.get("about me")

    # Activity: "Joined in December 2013, last active this month"
    activity = info.get("activity", "")
    joined_date = None
    last_active = None
    jm = re.search(r"Joined in\s+(.+?)(?:,|$)", activity)
    if jm:
        joined_date = parse_date(jm.group(1).strip())
    am = re.search(r"last active\s+(.+)", activity)
    if am:
        last_active = parse_date(am.group(1).strip())

    # Stats: ratings, avg, reviews
    stats_el = _first(doc,".profilePageUserStatsInfo")
    stats_text = molt(stats_el.text_content()) if stats_el else ""
    ratings_count = None
    avg_rating = None
    reviews_count = None
    rm = re.search(r"([\d,]+)\s+ratings?", stats_text or "")
    if rm:
        ratings_count = parse_int(rm.group(1))
    avm = re.search(r"\(([\d.]+)\s+avg\)", stats_text or "")
    if avm:
        avg_rating = avm.group(1)
    revm = re.search(r"([\d,]+)\s+reviews?", stats_text or "")
    if revm:
        reviews_count = parse_int(revm.group(1))

    # Friends count from link text: "Kirill's Friends (138)"
    friends_count = None
    for a in doc.cssselect("a[href*='/friend/user/']"):
        fm = re.search(r"\((\d+)\)", a.text_content())
        if fm:
            friends_count = int(fm.group(1))
            break

    # Parse profile sections — h2 lives inside .bigBox; content is in .bigBoxBody
    sections: dict[str, Any] = {}
    for hdr in doc.cssselect("h2.brownBackground, .bigBoxHeader"):
        label = (molt(hdr.text_content()) or "").lower()
        # Walk up to find ancestor div.bigBox
        parent_box = None
        el = hdr.getparent()
        while el is not None:
            classes = (el.get("class") or "").split()
            if el.tag == "div" and "bigBox" in classes:
                parent_box = el
                break
            el = el.getparent()
        if parent_box is not None:
            body_els = parent_box.cssselect(".bigBoxBody, .bigBoxContent")
            if body_els:
                sections[label] = body_els[0]
        else:
            sib = hdr.getnext()
            if sib is not None:
                sections[label] = sib

    # Favorite books
    favorite_books: list[dict[str, Any]] = []
    for key, body in sections.items():
        if "favorite" in key and "book" in key:
            for a in body.cssselect('a[href*="/book/show/"]'):
                bimg = _first(a, "img")
                btitle = bimg.get("alt") if bimg else molt(a.text_content())
                bm = re.search(r"/book/show/(\d+)", a.get("href", ""))
                if bm and btitle:
                    cover = bimg.get("src") if bimg else None
                    bid = bm.group(1)
                    favorite_books.append({
                        "id": bid,
                        "name": btitle,
                        "image": cover,
                        "url": f"{BASE}/book/show/{bid}",
                    })

    # Currently reading — each .Updates div has a book + timestamp
    currently_reading: list[dict[str, Any]] = []
    for key, body in sections.items():
        if "currently reading" in key:
            for update in body.cssselect(".Updates"):
                book_link = _first(update, "a.bookTitle")
                if not book_link:
                    continue
                btitle = molt(book_link.text_content())
                bm = re.search(r"/book/show/(\d+)", book_link.get("href", ""))
                if not bm or not btitle:
                    continue

                date_el = _first(update, "a.updatedTimestamp")
                date_added = parse_date(molt(date_el.text_content())) if date_el else None

                author_link = _first(update, "a.authorName")
                author_name = molt(author_link.text_content()) if author_link else None
                author_id = None
                if author_link:
                    am = re.search(r"/author/show/(\d+)", author_link.get("href", ""))
                    if am:
                        author_id = am.group(1)

                bid = bm.group(1)
                entry: dict[str, Any] = {
                    "id": bid,
                    "name": btitle,
                    "url": f"{BASE}/book/show/{bid}",
                    "dateAdded": date_added,
                }
                if author_name:
                    entry["author"] = author_name
                    entry["written_by"] = {"id": author_id or author_name, "name": author_name}
                currently_reading.append(entry)

    # Favorite genres
    favorite_genres: list[str] = []
    for key, body in sections.items():
        if "genre" in key:
            favorite_genres = [
                molt(a.text_content()) for a in body.cssselect("a") if molt(a.text_content())
            ]

    uid = user_id
    person: dict[str, Any] = {
        "id": uid,
        "name": name,
        "image": photo_url,
        "url": f"{BASE}/user/show/{uid}",
        "gender": gender,
        "age": age,
        "birthday": birthday,
        "location": molt(location),
        "website": molt(website),
        "about": molt(about),
        "interests": molt(interests),
        "joinedDate": joined_date,
        "lastActive": last_active,
        "ratingsCount": ratings_count,
        "avgRating": avg_rating,
        "reviewsCount": reviews_count,
        "friendsCount": friends_count,
        "favoriteGenres": favorite_genres if favorite_genres else None,
        "accounts": [{
            "id": uid,
            "name": name,
            "handle": handle,
            "url": f"{BASE}/user/show/{uid}",
            "image": photo_url,
        }],
    }
    if favorite_books:
        person["favorite_books"] = favorite_books
    if currently_reading:
        person["currently_reading"] = currently_reading

    return person


# ---------------------------------------------------------------------------
# Friends
# ---------------------------------------------------------------------------


def _parse_friends_page(doc: HtmlElement, user_id: str) -> list[dict[str, Any]]:
    """Parse a single page of friends from the #friendTable, extracting rich data."""
    friends: list[dict[str, Any]] = []
    seen: set[str] = set()

    table = _first(doc,"#friendTable")
    rows = table.cssselect("tr") if table else []

    for row in rows:
        tds = row.cssselect("td")
        if len(tds) < 2:
            continue

        # td[0]: avatar image + user link
        # td[1]: name, book count, friend count, location
        user_link = _first(tds[1], 'a[href*="/user/show/"]') if len(tds) > 1 else None
        if not user_link:
            user_link = _first(row, 'a[href*="/user/show/"]')
        if not user_link:
            continue
        href = user_link.get("href", "")
        m = re.search(r"/user/show/(\d+)", href)
        if not m:
            continue
        uid = m.group(1)
        if uid == user_id or uid in seen:
            continue

        name = molt(user_link.text_content())
        if not name or name.lower() in ("profile", "view profile"):
            continue
        seen.add(uid)

        # Photo from td[0]
        photo_img = _first(tds[0], "img") if tds else None
        photo_url = photo_img.get("src") if photo_img else None
        if photo_url:
            photo_url = re.sub(r"p2/", "p7/", photo_url)

        # Book count and friend count from td[1] links
        books_count = None
        friends_count = None
        location = None

        books_link = _first(tds[1], 'a[href*="/review/list/"]') if len(tds) > 1 else None
        if books_link:
            bm = re.search(r"(\d+)", books_link.text_content())
            if bm:
                books_count = int(bm.group(1))

        friends_link = _first(tds[1], 'a[href*="/friend/"]') if len(tds) > 1 else None
        if friends_link:
            fm = re.search(r"(\d+)", friends_link.text_content())
            if fm:
                friends_count = int(fm.group(1))

        # Location: text after the last <a> and before end of td[1]
        if len(tds) > 1:
            td_text = tds[1].text_content().strip()
            lines = [l.strip() for l in td_text.split("\n") if l.strip()]
            # Location is usually the last line that isn't a link text
            link_texts = {molt(a.text_content()) for a in tds[1].cssselect("a")}
            for line in reversed(lines):
                cleaned = molt(line)
                if cleaned and cleaned not in link_texts and not re.match(r"^\d+\s+(books?|friends?)", cleaned):
                    location = cleaned
                    break

        # Currently reading from td[2]
        currently_reading = None
        if len(tds) > 2:
            for book_link in tds[2].cssselect('a[href*="/book/show/"]'):
                book_text = molt(book_link.text_content())
                if book_text:
                    bm2 = re.search(r"/book/show/(\d+)", book_link.get("href", ""))
                    bid = bm2.group(1) if bm2 else None
                    currently_reading = {
                        "id": bid,
                        "name": book_text,
                        "url": f"{BASE}/book/show/{bid}" if bid else None,
                    }
                    break

        friend: dict[str, Any] = {
            "id": uid,
            "name": name,
            "image": photo_url,
            "url": f"{BASE}/user/show/{uid}",
            "location": location,
            "booksCount": books_count,
            "friendsCount": friends_count,
        }
        if currently_reading:
            friend["currently_reading"] = currently_reading
        friends.append(friend)

    if friends:
        return friends

    # Fallback: plain link scan if table structure changed
    for link in doc.cssselect('a[href*="/user/show/"]'):
        href = link.get("href", "")
        m = re.search(r"/user/show/(\d+)", href)
        if not m:
            continue
        uid = m.group(1)
        if uid == user_id or uid in seen:
            continue
        name = molt(link.text_content())
        if not name or name.lower() in ("profile", "view profile"):
            continue
        seen.add(uid)
        friends.append({"id": uid, "name": name, "url": f"{BASE}/user/show/{uid}"})

    return friends


def _list_friends(
    user_id: str,
    page: int = 0,
    cookie_header: str | None = None,
    *,
    params: dict | None = None,
) -> list[dict[str, Any]]:
    """
    List a user's friends. page=0 (default) fetches all pages.
    page=N fetches only that page.
    """
    cookie_header = _require_cookies(cookie_header, params, "list_friends")

    if page > 0:
        resp = http.get(f"{BASE}/friend/user/{user_id}?page={page}", cookies=cookie_header, **_H)
        status, html_text = resp["status"], resp["body"]
        if status != 200:
            raise RuntimeError(f"Friends page returned {status}")
        _require_login(html_text)
        return _parse_friends_page(_parse(html_text), user_id)

    # Auto-paginate
    all_friends: list[dict[str, Any]] = []
    seen: set[str] = set()
    with http.client(cookies=cookie_header) as client:
        for p in range(1, MAX_PAGES + 1):
            status, html_text = _fetch(client, f"{BASE}/friend/user/{user_id}?page={p}")
            if status != 200:
                break
            if p == 1:
                _require_login(html_text)
            page_friends = _parse_friends_page(_parse(html_text), user_id)
            for f in page_friends:
                if f["id"] not in seen:
                    seen.add(f["id"])
                    all_friends.append(f)
            if not page_friends or not _has_next(html_text):
                break

    return all_friends


# ---------------------------------------------------------------------------
# Search people
# ---------------------------------------------------------------------------


def _search_people(
    query: str,
    limit: int = 10,
    cookie_header: str | None = None,
    *,
    params: dict | None = None,
) -> list[dict[str, Any]]:
    cookie_header = cookie_header or get_cookies(params)
    url = f"{BASE}/search?q={quote_plus(query)}&search_type=people"
    resp = http.get(url, cookies=cookie_header, **_H)
    status, html_text = resp["status"], resp["body"]
    if status != 200:
        raise RuntimeError(f"Search returned {status}")

    doc = _parse(html_text)
    results: list[dict[str, Any]] = []
    seen: set[str] = set()

    for link in doc.cssselect('a[href*="/user/show/"]'):
        href = link.get("href", "")
        m = re.search(r"/user/show/(\d+)(?:-[^/]*)?", href)
        if not m:
            continue
        uid = m.group(1)
        if uid in seen:
            continue
        name = molt(link.text_content())
        if not name or name.lower() in ("profile", "view profile", "compare books"):
            continue
        seen.add(uid)
        results.append({"id": uid, "name": name, "url": f"{BASE}/user/show/{uid}"})
        if len(results) >= limit:
            break

    return results


# ---------------------------------------------------------------------------
# Email lookup (resolve_email)
# ---------------------------------------------------------------------------


def _resolve_email(
    email: str,
    cookie_header: str | None = None,
    *,
    params: dict | None = None,
) -> list[dict[str, Any]]:
    """Look up Goodreads accounts by email address."""
    cookie_header = _require_cookies(cookie_header, params, "resolve_email")

    with http.client(cookies=cookie_header) as client:
        # Step 1: load the find_friend page to get the CSRF token (n=)
        status, form_html = _fetch(client, f"{BASE}/friend/find_friend")
        if status != 200:
            raise RuntimeError(f"Find friend page returned {status}")

        form_doc = _parse(form_html)
        n_input = _first(form_doc, 'input[name="n"]')
        n_token = n_input.get("value", "") if n_input else ""

        # Step 2: submit the search (cookie jar carries Set-Cookie from step 1)
        search_url = (
            f"{BASE}/friend/find_friend?utf8=%E2%9C%93"
            f"&n={n_token}&q={quote_plus(email)}"
        )
        status2, results_html = _fetch(client, search_url)
        if status2 != 200:
            raise RuntimeError(f"Friend search returned {status2}")

    doc = _parse(results_html)
    table = _first(doc,"table.tableList")
    if not table:
        return []

    people: list[dict[str, Any]] = []
    for row in table.cssselect("tr"):
        user_link = _first(row, 'a[href*="/user/show/"]')
        if not user_link:
            continue
        href = user_link.get("href", "")
        m = re.search(r"/user/show/(\d+)", href)
        if not m:
            continue
        uid = m.group(1)
        name = molt(user_link.text_content())
        if not name:
            img = _first(row, "img")
            name = img.get("alt") if img else None
        if not name:
            continue

        img = _first(row, "img[src*='/users/']")
        photo_url = img.get("src") if img else None

        row_text = row.text_content()
        books_m = re.search(r"([\d,]+)\s+books?", row_text)
        friends_m = re.search(r"([\d,]+)\s+friends?", row_text)

        # Location: text after the stats line, before action buttons
        location = None
        for td in row.cssselect("td"):
            lines = [l.strip() for l in td.text_content().split("\n") if l.strip()]
            for line in lines:
                if (
                    line != name
                    and not re.match(r"[\d,]+\s+(books?|friends?)", line)
                    and line not in ("|",)
                    and "Add" not in line
                    and "Follow" not in line
                    and "compare" not in line.lower()
                ):
                    candidate = line.strip()
                    if len(candidate) > 2 and not candidate.isdigit():
                        location = candidate
                        break

        people.append({
            "id": uid,
            "name": name,
            "image": photo_url,
            "url": f"{BASE}/user/show/{uid}",
            "location": location,
            "booksCount": parse_int(books_m.group(1)) if books_m else None,
            "friendsCount": parse_int(friends_m.group(1)) if friends_m else None,
            "email": email,
        })

    return people


# ---------------------------------------------------------------------------
# Shelves
# ---------------------------------------------------------------------------


def _list_shelves(
    user_id: str,
    cookie_header: str | None = None,
    *,
    params: dict | None = None,
) -> list[dict[str, Any]]:
    cookie_header = cookie_header or get_cookies(params)
    url = f"{BASE}/user/show/{user_id}"
    resp = http.get(url, cookies=cookie_header, **_H)
    status, html_text = resp["status"], resp["body"]
    if status != 200:
        raise RuntimeError(f"Profile returned {status}")

    doc = _parse(html_text)
    seen: set[str] = set()
    shelves: list[dict[str, Any]] = []
    for link in doc.cssselect('a[href*="shelf="], a.actionLinkLite.userShowPageShelfListItem'):
        href = link.get("href", "")
        m = re.search(r"/review/list/\d+\?[^\"]*shelf=([^&\s\"']+)", href)
        if not m:
            continue
        shelf_id = m.group(1)
        if shelf_id in seen:
            continue
        seen.add(shelf_id)
        name = molt(link.text_content())
        if name and name.lower() in ("view shelf", "shelf"):
            continue
        if name and re.search(r"\(\d+\)\s*$", name):
            name = re.sub(r"\s*\(\d+\)\s*$", "", name).strip()
        count_m = re.search(r"\(([\d,]+)\)", link.text_content())
        book_count = parse_int(count_m.group(1)) if count_m else None
        shelves.append({
            "id": f"{user_id}:{shelf_id}",
            "name": name or shelf_id,
            "bookCount": book_count,
            "url": _abs_url(href),
        })

    return shelves


# ---------------------------------------------------------------------------
# Books / Reviews / Shelf books  (all use /review/list/)
# ---------------------------------------------------------------------------


def _extract_date(row: Any, field_class: str) -> str | None:
    """Extract a clean date string from a td.field cell."""
    td = _first(row, f"td.field.{field_class}")
    if not td:
        return None
    # Prefer span[title] which has the full date
    span = _first(td, "span[title]")
    if span:
        return molt(span.get("title") or span.text_content())
    # Fallback: look for non-grey text
    for span in td.cssselect("span"):
        text = molt(span.text_content())
        if text and text != "not set":
            return text
    return None


def _extract_rating(row: Any) -> int | None:
    """Extract user's rating from the stars data-rating attribute."""
    stars = _first(row, ".stars[data-rating]")
    if stars:
        val = stars.get("data-rating", "0")
        r = int(val) if val.isdigit() else 0
        return r if r > 0 else None
    return None


def _extract_review_text(row: Any) -> str | None:
    """Extract review text, ignoring 'Write a review' placeholder."""
    td = _first(row, "td.field.review")
    if not td:
        return None
    text = molt(td.text_content())
    if not text:
        return None
    # Strip the "review" label prefix
    text = re.sub(r"^review\s*", "", text)
    # Strip trailing [edit]
    text = re.sub(r"\s*\[edit\]\s*$", "", text)
    if not text or text == "Write a review":
        return None
    return text


def _extract_shelf(row: Any) -> str | None:
    """Extract shelf name from the shelves field."""
    td = _first(row, "td.field.shelves")
    if not td:
        return None
    text = molt(td.text_content())
    if not text:
        return None
    text = re.sub(r"^shelves?\s*", "", text)
    text = re.sub(r"\s*\[edit\]\s*$", "", text)
    return text if text else None


def _parse_book_rows(doc: HtmlElement, as_reviews: bool = False) -> list[dict[str, Any]]:
    """Parse tr.bookalike rows into book or review dicts."""
    rows = doc.cssselect("tr.bookalike")
    items: list[dict[str, Any]] = []

    for row in rows:
        book_id = row.get("data-resource-id")
        if not book_id:
            for a in row.cssselect('a[href*="/book/show/"]'):
                m = re.search(r"/book/show/(\d+)", a.get("href", ""))
                if m:
                    book_id = m.group(1)
                    break
        if not book_id:
            continue

        title_el = _first(row, "td.field.title a, .title a, a.bookTitle")
        title = molt(title_el.get("title") or (title_el.text_content() if title_el else None))

        author_el = _first(row, "td.field.author a, .author a, a.authorName")
        author_raw = molt(author_el.text_content() if author_el else None)
        author = _flip_name(author_raw) if author_raw else None
        author_id = None
        author_url = None
        if author_el:
            href = author_el.get("href", "")
            am = re.search(r"/author/show/(\d+)", href)
            if am:
                author_id = am.group(1)
                author_url = _abs_url(href)

        rating = _extract_rating(row)
        date_added = _extract_date(row, "date_added")
        date_read = _extract_date(row, "date_read")
        date_started = _extract_date(row, "date_started")
        shelf = _extract_shelf(row)

        cover_img = _first(row, "td.field.cover img")
        cover_url = cover_img.get("src") if cover_img else None
        if cover_url:
            cover_url = re.sub(r"\._SY\d+_", "._SY475_", cover_url)

        isbn = _field_value(row, "isbn")
        isbn13 = _field_value(row, "isbn13")
        avg_rating = _field_value(row, "avg_rating")
        num_pages = _field_value(row, "num_pages")
        date_pub = _field_value(row, "date_pub")

        # Shape-native relation dict for author
        written_by = None
        if author_id or author:
            written_by = {"id": author_id or author, "name": author}
            if author_url:
                written_by["url"] = author_url

        if as_reviews:
            review_id = None
            for a in row.cssselect('a[href*="/review/show/"]'):
                m = re.search(r"/review/show/(\d+)", a.get("href", ""))
                if m:
                    review_id = m.group(1)
                    break
            review_text = _extract_review_text(row)
            entry: dict[str, Any] = {
                "id": review_id,
                "name": f"Review of {title}" if title else "Review",
                "content": review_text,
                "url": f"{BASE}/review/show/{review_id}" if review_id else None,
                "author": author,
                "published": date_read or date_added,
                "rating": rating,
                "dateRead": date_read,
                "dateStarted": date_started,
                "dateAdded": date_added,
                "shelfName": shelf,
            }
            if written_by:
                entry["written_by"] = written_by
            entry["references"] = {
                "id": str(book_id),
                "name": title,
                "url": f"{BASE}/book/show/{book_id}",
                "image": cover_url,
                "author": author,
            }
            items.append(entry)
        else:
            entry = {
                "id": str(book_id),
                "name": title,
                "image": cover_url,
                "url": f"{BASE}/book/show/{book_id}",
                "author": author,
                "isbn": isbn,
                "isbn13": isbn13,
                "userRating": rating,
                "averageRating": avg_rating,
                "pages": parse_int(num_pages),
                "published": date_pub,
                "dateAdded": date_added,
                "dateRead": date_read,
                "dateStarted": date_started,
                "shelf": shelf,
            }
            if written_by:
                entry["written_by"] = written_by
            items.append(entry)

    return items


def _fetch_book_pages(
    client,
    url_template: str,
    page: int,
    as_reviews: bool,
) -> list[dict[str, Any]]:
    """Fetch one or all pages from /review/list/ endpoint."""
    if page > 0:
        status, html_text = _fetch(client, url_template.format(page=page))
        if status != 200:
            raise RuntimeError(f"Page returned {status}")
        _require_login(html_text)
        return _parse_book_rows(_parse(html_text), as_reviews)

    # Auto-paginate
    all_items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for p in range(1, MAX_PAGES + 1):
        status, html_text = _fetch(client, url_template.format(page=p))
        if status != 200:
            break
        if p == 1:
            _require_login(html_text)
        items = _parse_book_rows(_parse(html_text), as_reviews)
        for item in items:
            key = item.get("id", "")
            if key and key not in seen_ids:
                seen_ids.add(key)
                all_items.append(item)
        if not items or not _has_next(html_text):
            break

    return all_items


def _list_books(
    user_id: str,
    shelf: str = "all",
    sort: str = "date_added",
    page: int = 0,
    cookie_header: str | None = None,
    *,
    params: dict | None = None,
) -> list[dict[str, Any]]:
    """List a user's books. page=0 fetches all pages."""
    cookie_header = _require_cookies(cookie_header, params, "list_books")
    url_tpl = f"{BASE}/review/list/{user_id}?shelf={shelf}&sort={sort}&page={{page}}&per_page={PER_PAGE_BOOKS}"
    with http.client(cookies=cookie_header) as client:
        return _fetch_book_pages(client, url_tpl, page, as_reviews=False)


def _list_reviews(
    user_id: str,
    sort: str = "date",
    page: int = 0,
    cookie_header: str | None = None,
    *,
    params: dict | None = None,
) -> list[dict[str, Any]]:
    """List a user's reviews. page=0 fetches all pages."""
    cookie_header = _require_cookies(cookie_header, params, "list_reviews")
    url_tpl = f"{BASE}/review/list/{user_id}?shelf=all&sort={sort}&page={{page}}&per_page={PER_PAGE_BOOKS}"
    with http.client(cookies=cookie_header) as client:
        return _fetch_book_pages(client, url_tpl, page, as_reviews=True)


def _list_shelf_books(
    user_id: str,
    shelf_name: str,
    page: int = 0,
    cookie_header: str | None = None,
    *,
    params: dict | None = None,
) -> list[dict[str, Any]]:
    """List books on a specific shelf. page=0 fetches all pages."""
    cookie_header = _require_cookies(cookie_header, params, "list_shelf_books")
    url_tpl = f"{BASE}/review/list/{user_id}?shelf={shelf_name}&page={{page}}&per_page={PER_PAGE_BOOKS}"
    with http.client(cookies=cookie_header) as client:
        return _fetch_book_pages(client, url_tpl, page, as_reviews=False)


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------


def _list_groups(
    cookie_header: str | None = None,
    *,
    params: dict | None = None,
) -> list[dict[str, Any]]:
    """List the authenticated user's groups."""
    cookie_header = _require_cookies(cookie_header, params, "list_groups")
    url = f"{BASE}/group?tab=my_groups"
    resp = http.get(url, cookies=cookie_header, **_H)
    status, html_text = resp["status"], resp["body"]
    if status != 200:
        raise RuntimeError(f"Groups page returned {status}")

    doc = _parse(html_text)
    groups: list[dict[str, Any]] = []
    seen: set[str] = set()

    for wrapper in doc.cssselect(".groupListItemWrapper"):
        link = _first(wrapper, 'a[href*="/group/show/"]')
        if not link:
            continue
        href = link.get("href", "")
        m = re.search(r"/group/show/(\d+)", href)
        if not m:
            continue
        gid = m.group(1)
        if gid in seen:
            continue
        seen.add(gid)

        lines = [l.strip() for l in wrapper.text_content().split("\n") if l.strip()]
        name = lines[0] if lines else None
        members = None
        last_active = None
        for line in lines[1:]:
            mm = re.match(r"([\d,]+)\s+members?", line)
            if mm:
                members = parse_int(mm.group(1))
            if line.startswith("Active"):
                last_active = line

        img = _first(wrapper, "img")
        image_url = img.get("src") if img else None

        groups.append({
            "id": gid,
            "name": name,
            "image": image_url,
            "url": _abs_url(f"/group/show/{gid}"),
            "memberCount": members,
            "lastActive": last_active,
        })

    return groups


# ---------------------------------------------------------------------------
# Following / Followers
# ---------------------------------------------------------------------------


def _parse_follow_page(
    doc: HtmlElement, owner_id: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse a followers/following page, returning (users, authors) separately."""
    users: list[dict[str, Any]] = []
    authors: list[dict[str, Any]] = []
    seen: set[str] = set()

    for link in doc.cssselect('a[href*="/user/show/"], a[href*="/author/show/"]'):
        href = link.get("href", "")
        name = molt(link.text_content())
        if not name or name.lower() in ("profile", "view profile"):
            continue
        m = re.search(r"/(user|author)/show/(\d+)", href)
        if not m:
            continue
        kind, uid = m.group(1), m.group(2)
        key = f"{kind}:{uid}"
        if key in seen or uid == owner_id:
            continue
        seen.add(key)

        img_parent = link.getparent()
        img_els = img_parent.cssselect("img") if img_parent is not None else []
        photo = img_els[0].get("src") if img_els else None

        if kind == "author":
            authors.append({
                "id": uid,
                "name": name,
                "image": photo,
                "url": f"{BASE}/author/show/{uid}",
            })
        else:
            users.append({
                "id": uid,
                "name": name,
                "image": photo,
                "url": f"{BASE}/user/show/{uid}",
            })

    return users, authors


def _list_following(
    user_id: str,
    cookie_header: str | None = None,
    *,
    params: dict | None = None,
) -> list[dict[str, Any]]:
    """List accounts (users + authors) the user is following."""
    cookie_header = cookie_header or get_cookies(params)
    url = f"{BASE}/user/{user_id}/following"
    resp = http.get(url, cookies=cookie_header, **_H)
    status, html_text = resp["status"], resp["body"]
    if status != 200:
        raise RuntimeError(f"Following page returned {status}")

    doc = _parse(html_text)
    users, authors = _parse_follow_page(doc, user_id)
    results: list[dict[str, Any]] = []
    for u in users:
        u["type"] = "user"
        results.append(u)
    for a in authors:
        a["type"] = "author"
        results.append(a)
    return results


def _list_followers(
    user_id: str,
    cookie_header: str | None = None,
    *,
    params: dict | None = None,
) -> list[dict[str, Any]]:
    """List accounts following the user."""
    cookie_header = cookie_header or get_cookies(params)
    url = f"{BASE}/user/{user_id}/followers"
    resp = http.get(url, cookies=cookie_header, **_H)
    status, html_text = resp["status"], resp["body"]
    if status != 200:
        raise RuntimeError(f"Followers page returned {status}")

    doc = _parse(html_text)
    users, authors = _parse_follow_page(doc, user_id)
    results: list[dict[str, Any]] = []
    for u in users:
        u["type"] = "user"
        results.append(u)
    for a in authors:
        a["type"] = "author"
        results.append(a)
    return results


# ---------------------------------------------------------------------------
# Quotes (user's liked/saved quotes)
# ---------------------------------------------------------------------------


def _list_quotes(
    user_id: str,
    cookie_header: str | None = None,
    *,
    params: dict | None = None,
) -> list[dict[str, Any]]:
    """List a user's liked/saved quotes."""
    cookie_header = cookie_header or get_cookies(params)
    url = f"{BASE}/quotes/list/{user_id}"
    resp = http.get(url, cookies=cookie_header, **_H)
    status, html_text = resp["status"], resp["body"]
    if status != 200:
        raise RuntimeError(f"Quotes page returned {status}")

    doc = _parse(html_text)
    quotes: list[dict[str, Any]] = []

    for qt in doc.cssselect(".quoteText"):
        # Extract quote text (before the ― author attribution)
        text_parts = []
        for child in qt.children:
            if hasattr(child, "name"):
                if child.name == "br":
                    text_parts.append("\n")
                elif child.name == "span" and "authorOrTitle" in (child.get("class") or []):
                    break
                elif child.name == "b":
                    text_parts.append(child.text_content())
                elif child.text_content().strip() == "\u2015":
                    break
                else:
                    text_parts.append(child.text_content())
            else:
                s = str(child)
                if "\u2015" in s:
                    text_parts.append(s.split("\u2015")[0])
                    break
                text_parts.append(s)

        text = "".join(text_parts).strip()
        text = re.sub(r'^[\s\u201c\u201d"]+|[\s\u201c\u201d"]+$', "", text)

        author_el = _first(qt, ".authorOrTitle")
        author_name = molt(author_el.text_content()) if author_el else None
        if author_name:
            author_name = author_name.rstrip(",")

        # Author link from the parent container
        parent = qt.getparent()
        author_links = parent.cssselect('a[href*="/author/show/"]') if parent is not None else []
        author_link = author_links[0] if author_links else None
        author_id = None
        if author_link is not None:
            am = re.search(r"/author/show/(\d+)", author_link.get("href", ""))
            if am:
                author_id = am.group(1)

        # Book link if present
        book_title = None
        book_id = None
        title_els = qt.cssselect('.authorOrTitle + .authorOrTitle, a[href*="/book/show/"]')
        title_el = title_els[0] if title_els else None
        if title_el is None and parent is not None:
            fallback = parent.cssselect('a[href*="/book/show/"]')
            title_el = fallback[0] if fallback else None
        if title_el:
            book_title = molt(title_el.text_content())
            bm = re.search(r"/book/show/(\d+)", title_el.get("href", ""))
            if bm:
                book_id = bm.group(1)

        if text:
            qid = f"{author_id or 'unknown'}:{text[:40]}"
            quote: dict[str, Any] = {
                "id": qid,
                "name": text[:80],
                "content": text,
                "author": author_name,
            }
            if author_id or author_name:
                quote["spoken_by"] = {
                    "id": author_id or author_name,
                    "name": author_name,
                    "url": f"{BASE}/author/show/{author_id}" if author_id else None,
                }
            if book_id:
                quote["appears_in"] = {
                    "id": book_id,
                    "name": book_title,
                    "url": f"{BASE}/book/show/{book_id}",
                }
            quotes.append(quote)

    return quotes
