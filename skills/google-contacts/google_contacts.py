"""Google Contacts skill — People API via http.get/post/patch/delete.

Auth token lives in params["auth"]["access_token"], injected by the engine
from the Mimestream OAuth provider (googleapis.com / contacts scope).
"""

import re

from agentos import http

BASE_URL = "https://people.googleapis.com/v1"

PERSON_FIELDS = ",".join([
    "names", "emailAddresses", "phoneNumbers", "organizations",
    "addresses", "birthdays", "urls", "photos", "biographies",
    "memberships", "metadata", "nicknames",
])


# ==============================================================================
# Internal helpers
# ==============================================================================


def _auth_header(params):
    auth = params.get("auth", {})
    bearer = auth.get("bearer")
    if bearer:
        return {"Authorization": bearer}
    token = auth.get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


def _url_to_platform(url):
    """Extract platform from URL domain: 'https://www.linkedin.com/in/joe' -> 'linkedin'."""
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
    patterns = [
        (re.compile(r"/(in|pub)/([^/?]+)"), 2),
        (re.compile(r"/users?/([^/?]+)"), 1),
        (re.compile(r"/profile/([^.?][^/?]*)"), 1),
        (re.compile(r"/@([^/?]+)"), 1),
        (re.compile(r"/people/([^/?]+)"), 1),
        (re.compile(r"https?://[^/]+/([^/?]+)"), 1),
    ]
    for pattern, group in patterns:
        m = pattern.search(url)
        if m:
            return m.group(group)
    return None


def _build_accounts(person):
    """Build account typed refs from emails, phones, and URLs."""
    accounts = []

    for email in person.get("emailAddresses", []):
        value = email.get("value")
        if not value:
            continue
        entry = {"handle": value, "platform": "email"}
        label = email.get("type")
        if label:
            entry["name"] = label
        accounts.append(entry)

    for phone in person.get("phoneNumbers", []):
        value = phone.get("value") or phone.get("canonicalForm")
        if not value:
            continue
        entry = {"handle": value, "platform": "phone"}
        label = phone.get("type")
        if label:
            entry["name"] = label
        accounts.append(entry)

    seen_platforms = set()
    for url_entry in person.get("urls", []):
        url = url_entry.get("value")
        if not url:
            continue
        platform = _url_to_platform(url)
        if not platform or platform in seen_platforms:
            continue
        seen_platforms.add(platform)
        username = _extract_username(url)
        entry = {"platform": platform, "url": url}
        if username:
            entry["handle"] = username
        entry["name"] = username or platform
        accounts.append(entry)

    return accounts


def _map_person(person):
    """Map a Google People API person to the agentOS person shape."""
    resource_name = person.get("resourceName", "")

    # Name
    names = person.get("names", [{}])
    name_obj = names[0] if names else {}
    display_name = name_obj.get("displayName") or ""
    first_name = name_obj.get("givenName")
    last_name = name_obj.get("familyName")
    middle_name = name_obj.get("middleName")

    # Fall back to organization name if no personal name
    if not display_name:
        orgs = person.get("organizations", [])
        if orgs:
            display_name = orgs[0].get("name", "")

    result = {
        "id": resource_name,
        "name": display_name,
        "firstName": first_name,
        "lastName": last_name,
        "middleName": middle_name,
    }

    # Nickname
    nicknames = person.get("nicknames", [])
    if nicknames:
        result["nickname"] = nicknames[0].get("value")

    # Birthday
    birthdays = person.get("birthdays", [])
    if birthdays:
        date_obj = birthdays[0].get("date", {})
        year = date_obj.get("year")
        month = date_obj.get("month")
        day = date_obj.get("day")
        if month and day:
            if year:
                result["birthday"] = f"{year:04d}-{month:02d}-{day:02d}"
            else:
                result["birthday"] = f"--{month:02d}-{day:02d}"

    # Notes / biography
    bios = person.get("biographies", [])
    if bios:
        result["notes"] = bios[0].get("value")

    # Photo
    photos = person.get("photos", [])
    if photos and not photos[0].get("default"):
        result["image"] = photos[0].get("url")

    # Accounts (emails, phones, URLs)
    accounts = _build_accounts(person)
    if accounts:
        result["accounts"] = accounts

    # Addresses -> location (first physical address)
    addresses = person.get("addresses", [])
    if addresses:
        addr = addresses[0]
        place = {"name": addr.get("formattedValue") or addr.get("city", "")}
        if addr.get("streetAddress"):
            place["fullAddress"] = addr.get("formattedValue", "")
        if addr.get("city"):
            place["name"] = addr["city"]
        result["location"] = place

    # Organization + job title -> roles
    orgs = person.get("organizations", [])
    if orgs:
        roles = []
        for org in orgs:
            role = {}
            title = org.get("title")
            dept = org.get("department")
            org_name = org.get("name")
            if title:
                role["title"] = title
            if dept:
                role["department"] = dept
            if org_name:
                role["organization"] = {"name": org_name}
            if org.get("startDate"):
                sd = org["startDate"]
                if sd.get("year"):
                    role["startDate"] = f"{sd['year']:04d}-{sd.get('month', 1):02d}-{sd.get('day', 1):02d}"
            if org.get("endDate"):
                ed = org["endDate"]
                if ed.get("year"):
                    role["endDate"] = f"{ed['year']:04d}-{ed.get('month', 1):02d}-{ed.get('day', 1):02d}"
            if role:
                roles.append(role)
        if roles:
            result["roles"] = roles

    return result


# ==============================================================================
# Build request bodies
# ==============================================================================


def _build_person_body(*, first_name=None, last_name=None, organization=None,
                       job_title=None, department=None, emails=None, phones=None,
                       addresses=None, urls=None, birthday=None, notes=None):
    """Build a Google People API Person resource body from params."""
    body = {}

    if first_name is not None or last_name is not None:
        name = {}
        if first_name is not None:
            name["givenName"] = first_name
        if last_name is not None:
            name["familyName"] = last_name
        body["names"] = [name]

    if organization is not None or job_title is not None or department is not None:
        org = {}
        if organization is not None:
            org["name"] = organization
        if job_title is not None:
            org["title"] = job_title
        if department is not None:
            org["department"] = department
        body["organizations"] = [org]

    if emails is not None:
        body["emailAddresses"] = [
            {"value": e["value"], "type": e.get("type", "other")}
            for e in emails
        ]

    if phones is not None:
        body["phoneNumbers"] = [
            {"value": p["value"], "type": p.get("type", "other")}
            for p in phones
        ]

    if addresses is not None:
        body["addresses"] = [
            {k: v for k, v in a.items() if v is not None}
            for a in addresses
        ]

    if urls is not None:
        body["urls"] = [
            {"value": u["value"], "type": u.get("type", "other")}
            for u in urls
        ]

    if birthday is not None:
        parts = birthday.split("-")
        if len(parts) == 3:
            body["birthdays"] = [{"date": {
                "year": int(parts[0]),
                "month": int(parts[1]),
                "day": int(parts[2]),
            }}]

    if notes is not None:
        body["biographies"] = [{"value": notes, "contentType": "TEXT_PLAIN"}]

    return body


def _update_person_fields(body):
    """Derive updatePersonFields mask from a request body."""
    field_map = {
        "names": "names",
        "organizations": "organizations",
        "emailAddresses": "emailAddresses",
        "phoneNumbers": "phoneNumbers",
        "addresses": "addresses",
        "urls": "urls",
        "birthdays": "birthdays",
        "biographies": "biographies",
    }
    return ",".join(field_map[k] for k in body if k in field_map)


# ==============================================================================
# Operations
# ==============================================================================


def list_contacts(*, limit=100, page_token=None, **params):
    """List contacts sorted by last modified."""
    headers = _auth_header(params)
    query = {
        "personFields": PERSON_FIELDS,
        "pageSize": str(min(limit, 1000)),
        "sortOrder": "LAST_MODIFIED_DESCENDING",
    }
    if page_token:
        query["pageToken"] = page_token

    resp = http.get(
        f"{BASE_URL}/people/me/connections",
        params=query,
        **http.headers(accept="json", extra=headers),
    )
    data = resp["json"]
    connections = data.get("connections", [])
    return [_map_person(p) for p in connections]


def get_contact(*, id, **params):
    """Get full details of a specific contact."""
    headers = _auth_header(params)
    resource = id if id.startswith("people/") else f"people/{id}"

    resp = http.get(
        f"{BASE_URL}/{resource}",
        params={"personFields": PERSON_FIELDS},
        **http.headers(accept="json", extra=headers),
    )
    return _map_person(resp["json"])


def search_contacts(*, query, limit=30, **params):
    """Search contacts by name, email, phone, or any text."""
    headers = _auth_header(params)
    query_params = {
        "query": query,
        "readMask": PERSON_FIELDS,
        "pageSize": str(min(limit, 30)),
    }

    resp = http.get(
        f"{BASE_URL}/people:searchContacts",
        params=query_params,
        **http.headers(accept="json", extra=headers),
    )
    data = resp["json"]
    results = data.get("results", [])
    return [_map_person(r.get("person", {})) for r in results]


def create_contact(*, first_name=None, last_name=None, organization=None,
                   job_title=None, department=None, emails=None, phones=None,
                   addresses=None, urls=None, birthday=None, notes=None, **params):
    """Create a new contact."""
    headers = _auth_header(params)
    body = _build_person_body(
        first_name=first_name, last_name=last_name, organization=organization,
        job_title=job_title, department=department, emails=emails, phones=phones,
        addresses=addresses, urls=urls, birthday=birthday, notes=notes,
    )

    resp = http.post(
        f"{BASE_URL}/people:createContact",
        params={"personFields": PERSON_FIELDS},
        json=body,
        **http.headers(accept="json", extra=headers),
    )
    return _map_person(resp["json"])


def update_contact(*, id, first_name=None, last_name=None, organization=None,
                   job_title=None, department=None, emails=None, phones=None,
                   addresses=None, urls=None, birthday=None, notes=None, **params):
    """Update an existing contact. Fetches current etag first."""
    headers = _auth_header(params)
    resource = id if id.startswith("people/") else f"people/{id}"

    # Fetch current contact for etag (required by API)
    current = http.get(
        f"{BASE_URL}/{resource}",
        params={"personFields": PERSON_FIELDS},
        **http.headers(accept="json", extra=headers),
    )
    etag = current["json"].get("etag")

    body = _build_person_body(
        first_name=first_name, last_name=last_name, organization=organization,
        job_title=job_title, department=department, emails=emails, phones=phones,
        addresses=addresses, urls=urls, birthday=birthday, notes=notes,
    )
    body["etag"] = etag

    mask = _update_person_fields(body)

    resp = http.patch(
        f"{BASE_URL}/{resource}:updateContact",
        params={"updatePersonFields": mask, "personFields": PERSON_FIELDS},
        json=body,
        **http.headers(accept="json", extra=headers),
    )
    return _map_person(resp["json"])


def delete_contact(*, id, **params):
    """Delete a contact permanently."""
    headers = _auth_header(params)
    resource = id if id.startswith("people/") else f"people/{id}"

    http.delete(
        f"{BASE_URL}/{resource}:deleteContact",
        **http.headers(accept="json", extra=headers),
    )
    return {"status": "deleted", "id": resource}
