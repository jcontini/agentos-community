"""Apple Contacts skill — macOS Contacts via SQLite + Swift helpers.

SQL operations (list, search) read the AddressBook database directly.
Command operations (get, accounts, create, update, delete) call Swift
scripts that use the Contacts framework for full API access.
"""

import json
import os
import subprocess

from agentos import sql

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))


def _db_path(account):
    """Build the AddressBook database path for a given account ID."""
    return f"~/Library/Application Support/AddressBook/Sources/{account}/AddressBook-v22.abcddb"


def _swift(script, args=None, stdin_data=None):
    """Run a Swift script and return parsed JSON output."""
    cmd = ["swift", os.path.join(SKILL_DIR, script)]
    if args:
        cmd.extend(args)
    result = subprocess.run(
        cmd,
        input=stdin_data,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if result.returncode != 0:
        error = result.stderr.strip() or result.stdout.strip()
        try:
            return json.loads(error)
        except (json.JSONDecodeError, TypeError):
            return {"error": error or f"Swift script failed with exit code {result.returncode}"}
    return json.loads(result.stdout)


# ==============================================================================
# SQL operations
# ==============================================================================


def op_list_persons(*, account, query=None, organization=None, sort="modified",
                    limit=1000, connection=None, **kw):
    """List contacts from a specific account."""
    return sql.query("""
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
