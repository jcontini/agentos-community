"""Apple Contacts skill — macOS Contacts via SQLite + Swift helpers.

SQL operations (list, search) read the AddressBook database directly.
Command operations (get, accounts, create, update, delete) call Swift
scripts that use the Contacts framework for full API access.
"""

import json
import os

from agentos import shell, sql

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))


def _db_path(account):
    """Build the AddressBook database path for a given account ID."""
    return f"~/Library/Application Support/AddressBook/Sources/{account}/AddressBook-v22.abcddb"


def _swift(script, args=None, stdin_data=None):
    """Run a Swift script and return parsed JSON output."""
    swift_args = [os.path.join(SKILL_DIR, script)]
    if args:
        swift_args.extend(args)
    result = shell.run("swift", swift_args, input=stdin_data, timeout=20)
    if result["exit_code"] != 0:
        error = result["stderr"].strip() or result["stdout"].strip()
        try:
            return json.loads(error)
        except (json.JSONDecodeError, TypeError):
            return {"error": error or f"Swift script failed with exit code {result['exit_code']}"}
    return json.loads(result["stdout"])


# ==============================================================================
# Shape mapping
# ==============================================================================


import re


_APPLE_LABEL_RE = re.compile(r"^_\$!<(.+)>!\$_$")
_GENERIC_LABELS = frozenset([
    "profile", "website", "homepage", "home-page", "company",
    "company-website", "business", "personal", "other", "home", "work",
])
_SERVICE_ALIASES = {
    "li": "linkedin", "lin": "linkedin", "linke": "linkedin", "linked": "linkedin",
    "linkedin": "linkedin",
    "fac": "facebook", "face": "facebook", "faceb": "facebook", "facebook": "facebook",
    "twit": "twitter", "twitt": "twitter", "twitter": "twitter", "x": "twitter",
    "ins": "instagram", "inst": "instagram", "insta": "instagram", "instagram": "instagram",
    "plus": "google-plus",
}
_USERNAME_PATTERNS = [
    (re.compile(r"/(in|pub)/([^/?]+)"), 2),
    (re.compile(r"/users?/([^/?]+)"), 1),
    (re.compile(r"/profile/([^.?][^/?]*)"), 1),
    (re.compile(r"profile\.php\?id=(\d+)"), 1),
    (re.compile(r"/@([^/?]+)"), 1),
    (re.compile(r"/people/([^/?]+)"), 1),
    (re.compile(r"https?://[^/]+/([^/?]+)"), 1),
]


def _parse_apple_label(label):
    """Parse Apple's _$!<Home>!$_ format to 'home', or return lowercased label."""
    if not label:
        return None
    m = _APPLE_LABEL_RE.match(label)
    if m:
        return m.group(1).lower()
    return label.lower()


def _url_to_platform(url):
    """Extract platform from URL domain: 'https://www.linkedin.com/in/joe' → 'linkedin'."""
    if not url:
        return None
    m = re.match(r"https?://(?:www\.)?([^/]+)", url)
    if not m:
        return None
    domain = m.group(1).split(".")[0]
    if domain == "x":
        return "twitter"
    if domain == "angel":
        return "angellist"
    return domain


def _extract_username(url):
    """Extract username from common URL patterns."""
    if not url:
        return None
    for pattern, group in _USERNAME_PATTERNS:
        m = pattern.search(url)
        if m:
            return m.group(group)
    return None


def _normalize_service(service):
    """Normalize truncated service names: 'li' → 'linkedin'."""
    if not service:
        return None
    key = service.lower()
    for prefix, normalized in _SERVICE_ALIASES.items():
        if key.startswith(prefix):
            return normalized
    return key


def _build_accounts(row):
    """Build account typed refs from phones, emails, URLs, and social profiles."""
    accounts = []

    # Phones
    for p in json.loads(row.get("phones_json") or "[]"):
        if not p.get("value"):
            continue
        entry = {"handle": p["value"], "platform": "phone"}
        label = _parse_apple_label(p.get("label"))
        if label:
            entry["name"] = label
        accounts.append(entry)

    # Emails
    for e in json.loads(row.get("emails_json") or "[]"):
        if not e.get("value"):
            continue
        entry = {"handle": e["value"], "platform": "email"}
        label = _parse_apple_label(e.get("label"))
        if label:
            entry["name"] = label
        accounts.append(entry)

    # URLs → accounts
    seen_platforms = set()
    for u in json.loads(row.get("urls_json") or "[]"):
        url = u.get("url")
        if not url:
            continue
        label = u.get("label", "")
        normalized_label = label.lower().replace(" ", "-") if label else ""

        if _APPLE_LABEL_RE.match(label or "") or normalized_label in _GENERIC_LABELS:
            platform = _url_to_platform(url)
        else:
            platform = normalized_label

        if not platform or platform in seen_platforms:
            continue
        seen_platforms.add(platform)

        entry = {"platform": platform, "url": url}
        username = _extract_username(url)
        if username:
            entry["handle"] = username
        accounts.append(entry)

    # Social profiles
    for sp in json.loads(row.get("social_json") or "[]"):
        username = sp.get("username")
        if not username:
            continue
        platform = _normalize_service(sp.get("service"))
        if not platform or platform in seen_platforms:
            continue
        seen_platforms.add(platform)
        accounts.append({"handle": username.lower(), "platform": platform})

    return accounts


def _map_person(row):
    """Map a SQL row to the person shape."""
    display_name = row.get("display_name") or row.get("organization") or ""

    result = {
        "id": row["id"],
        "name": display_name,
        "first_name": row.get("first_name"),
        "last_name": row.get("last_name"),
        "middle_name": row.get("middle_name"),
        "nickname": row.get("nickname"),
        "birthday": row.get("birthday"),
        "notes": row.get("notes"),
    }

    # Image from photo data
    if row.get("has_photo"):
        result["image"] = f"contacts://photo/{row['id']}"

    # Accounts as typed refs
    accounts = _build_accounts(row)
    if accounts:
        result["accounts"] = {"account[]": accounts}

    # Role (organization + job title + department) as typed ref
    org = row.get("organization")
    title = row.get("job_title")
    dept = row.get("department")
    if org or title:
        role = {}
        if title:
            role["title"] = title
        if dept:
            role["department"] = dept
        if org:
            role["organization"] = {"organization": {"name": org}}
        result["roles"] = {"role[]": [role]}

    return result


# ==============================================================================
# SQL operations
# ==============================================================================


def op_list_persons(*, account, query=None, organization=None, sort="modified",
                    limit=1000, connection=None, **kw):
    """List contacts from a specific account."""
    rows = sql.query("""
        SELECT
          r.ZUNIQUEID as id,
          r.ZFIRSTNAME as first_name,
          r.ZLASTNAME as last_name,
          r.ZMIDDLENAME as middle_name,
          r.ZNICKNAME as nickname,
          r.ZORGANIZATION as organization,
          r.ZJOBTITLE as job_title,
          r.ZDEPARTMENT as department,
          COALESCE(r.ZFIRSTNAME || ' ' || r.ZLASTNAME, r.ZORGANIZATION, r.ZFIRSTNAME, r.ZLASTNAME) as display_name,
          date(r.ZBIRTHDAY + 978307200, 'unixepoch') as birthday,
          datetime(r.ZMODIFICATIONDATE + 978307200, 'unixepoch') as modified_at,
          datetime(r.ZCREATIONDATE + 978307200, 'unixepoch') as created_at,
          CASE WHEN r.ZTHUMBNAILIMAGEDATA IS NOT NULL THEN 1 ELSE 0 END as has_photo,

          -- JSON arrays for phones, emails, URLs, social profiles
          (SELECT json_group_array(json_object('value', p.ZFULLNUMBER, 'label', p.ZLABEL))
           FROM ZABCDPHONENUMBER p WHERE p.ZOWNER = r.Z_PK) as phones_json,

          (SELECT json_group_array(json_object('value', e.ZADDRESS, 'label', e.ZLABEL))
           FROM ZABCDEMAILADDRESS e WHERE e.ZOWNER = r.Z_PK) as emails_json,

          (SELECT json_group_array(json_object('url', u.ZURL, 'label', u.ZLABEL))
           FROM ZABCDURLADDRESS u WHERE u.ZOWNER = r.Z_PK) as urls_json,

          (SELECT json_group_array(json_object('service', sp.ZSERVICENAME, 'username', sp.ZUSERNAME))
           FROM ZABCDSOCIALPROFILE sp WHERE sp.ZOWNER = r.Z_PK) as social_json

        FROM ZABCDRECORD r
        WHERE (r.ZUNIQUEID LIKE '%:ABPerson' OR r.ZUNIQUEID LIKE '%:ABInfo')
          AND (r.ZFIRSTNAME IS NOT NULL OR r.ZLASTNAME IS NOT NULL OR r.ZORGANIZATION IS NOT NULL)
        ORDER BY r.ZMODIFICATIONDATE DESC
        LIMIT :limit
    """, db=_db_path(account), params={"limit": limit})
    return [_map_person(r) for r in rows]


def op_search_persons(*, account, query, limit=1000, connection=None, **kw):
    """Search contacts by any text within a specific account."""
    return sql.query("""
        SELECT DISTINCT
          r.ZUNIQUEID as id,
          r.ZFIRSTNAME as first_name,
          r.ZLASTNAME as last_name,
          r.ZMIDDLENAME as middle_name,
          r.ZNICKNAME as nickname,
          r.ZORGANIZATION as organization,
          r.ZJOBTITLE as job_title,
          r.ZDEPARTMENT as department,
          COALESCE(r.ZFIRSTNAME || ' ' || r.ZLASTNAME, r.ZORGANIZATION) as display_name,
          date(r.ZBIRTHDAY + 978307200, 'unixepoch') as birthday,
          CASE WHEN r.ZTHUMBNAILIMAGEDATA IS NOT NULL THEN 1 ELSE 0 END as has_photo,

          -- JSON arrays for accounts building
          (SELECT json_group_array(json_object('value', p2.ZFULLNUMBER, 'label', p2.ZLABEL))
           FROM ZABCDPHONENUMBER p2 WHERE p2.ZOWNER = r.Z_PK) as phones_json,

          (SELECT json_group_array(json_object('value', e2.ZADDRESS, 'label', e2.ZLABEL))
           FROM ZABCDEMAILADDRESS e2 WHERE e2.ZOWNER = r.Z_PK) as emails_json,

          (SELECT json_group_array(json_object('url', u.ZURL, 'label', u.ZLABEL))
           FROM ZABCDURLADDRESS u WHERE u.ZOWNER = r.Z_PK) as urls_json,

          (SELECT json_group_array(json_object('service', sp.ZSERVICENAME, 'username', sp.ZUSERNAME))
           FROM ZABCDSOCIALPROFILE sp WHERE sp.ZOWNER = r.Z_PK) as social_json

        FROM ZABCDRECORD r
        LEFT JOIN ZABCDPHONENUMBER p ON p.ZOWNER = r.Z_PK
        LEFT JOIN ZABCDEMAILADDRESS e ON e.ZOWNER = r.Z_PK
        WHERE (r.ZUNIQUEID LIKE '%:ABPerson' OR r.ZUNIQUEID LIKE '%:ABInfo')
          AND (r.ZFIRSTNAME IS NOT NULL OR r.ZLASTNAME IS NOT NULL OR r.ZORGANIZATION IS NOT NULL)
          AND (
            r.ZFIRSTNAME LIKE '%' || :query || '%'
            OR r.ZLASTNAME LIKE '%' || :query || '%'
            OR r.ZORGANIZATION LIKE '%' || :query || '%'
            OR p.ZFULLNUMBER LIKE '%' || :query || '%'
            OR e.ZADDRESS LIKE '%' || :query || '%'
          )
        GROUP BY r.Z_PK
        ORDER BY COALESCE(r.ZLASTNAME, r.ZFIRSTNAME, r.ZORGANIZATION)
        LIMIT :limit
    """, db=_db_path(account), params={"query": query, "limit": limit})
    return [_map_person(r) for r in rows]


# ==============================================================================
# Swift command operations
# ==============================================================================


def op_get_person(*, id, **kw):
    """Get full contact details by ID."""
    return _swift("get_person.swift", args=[id])


def op_accounts(**kw):
    """List available contact accounts/containers."""
    return _swift("accounts.swift")


def op_create(*, account, first_name=None, last_name=None, organization=None,
              job_title=None, phones=None, emails=None, **kw):
    """Create a new contact in a specific account."""
    params = {"account": account}
    if first_name:
        params["first_name"] = first_name
    if last_name:
        params["last_name"] = last_name
    if organization:
        params["organization"] = organization
    if job_title:
        params["job_title"] = job_title
    if phones:
        params["phones"] = phones
    if emails:
        params["emails"] = emails
    return _swift("create.swift", stdin_data=json.dumps(params))


def op_update(*, id, first_name=None, last_name=None, organization=None,
              job_title=None, **kw):
    """Update scalar fields on a contact."""
    params = {"id": id}
    if first_name:
        params["first_name"] = first_name
    if last_name:
        params["last_name"] = last_name
    if organization:
        params["organization"] = organization
    if job_title:
        params["job_title"] = job_title
    return _swift("update.swift", stdin_data=json.dumps(params))


def op_delete(*, id, **kw):
    """Delete a contact."""
    params = {"id": id}
    return _swift("delete.swift", stdin_data=json.dumps(params))
