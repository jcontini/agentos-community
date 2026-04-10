"""Brave Browser skill — browsing history, profiles, cookies, and cookie key derivation.

Replaces YAML SQL, command, and steps operations with Python using the agentOS SDK.
Cookie decryption (cookie_get) lives in get-cookie.py and is untouched.
"""

import json
import os
import glob

from agentos import crypto, sql, connection, returns
from agentos.macos import keychain

HISTORY_DB = "~/Library/Application Support/BraveSoftware/Brave-Browser/Default/History"
COOKIES_DB = "~/Library/Application Support/BraveSoftware/Brave-Browser/Default/Cookies"
BRAVE_BASE = os.path.expanduser("~/Library/Application Support/BraveSoftware/Brave-Browser")


# ==============================================================================
# Browsing history
# ==============================================================================


def _map_webpage(row):
    """Map a SQL row to the webpage shape."""
    return {
        "id": row["url"],
        "name": row.get("title") or row["url"],
        "url": row["url"],
        "visitCount": row.get("visit_count"),
        "lastVisitUnix": row.get("last_visit_unix"),
    }


@returns("webpage[]")
@connection("history")
async def list_webpages(*, limit=200, **kw):
    """List recently visited pages from Brave browsing history."""
    db = HISTORY_DB
    rows = await sql.query("""
        SELECT url, title, visit_count,
               CAST((last_visit_time / 1000000) - 11644473600 AS INTEGER) AS last_visit_unix
        FROM urls
        WHERE hidden = 0
        ORDER BY last_visit_time DESC
        LIMIT :limit
    """, db=db, params={"limit": limit})
    return [_map_webpage(r) for r in rows]


@returns("webpage[]")
@connection("history")
async def search_webpages(*, query, limit=200, **kw):
    """Search Brave browsing history by URL or title."""
    db = HISTORY_DB
    rows = await sql.query("""
        SELECT url, title, visit_count,
               CAST((last_visit_time / 1000000) - 11644473600 AS INTEGER) AS last_visit_unix
        FROM urls
        WHERE hidden = 0
          AND (url LIKE :query OR title LIKE :query)
        ORDER BY last_visit_time DESC
        LIMIT :limit
    """, db=db, params={"query": f"%{query}%", "limit": limit})
    return [_map_webpage(r) for r in rows]


# ==============================================================================
# Profile discovery
# ==============================================================================


@returns({"name": "string", "path": "string"})
async def list_accounts(**kw):
    """List Brave browser profiles with their display name and email."""
    profiles = []
    for prefs_path in sorted(glob.glob(os.path.join(BRAVE_BASE, "*/Preferences"))):
        try:
            with open(prefs_path) as f:
                prefs = json.load(f)
            profile_dir = os.path.dirname(prefs_path)
            name = prefs.get("profile", {}).get("name", os.path.basename(profile_dir))
            email = prefs.get("profile", {}).get("user_name", "")
            profiles.append({"name": name, "email": email, "path": profile_dir})
        except Exception:
            pass
    return profiles


# ==============================================================================
# Cookie key derivation
# ==============================================================================


@returns({"key": "string"})
async def get_cookie_key(**kw):
    """Derive the AES-128 decryption key for Brave cookies on macOS.

    Reads the password from macOS Keychain ("Brave Safe Storage" / "Brave"),
    then runs PBKDF2-HMAC-SHA1 with salt "saltysalt" and 1003 iterations.
    Returns the hex-encoded 16-byte key.
    """
    password = await keychain.read(service="Brave Safe Storage", account="Brave")
    hex_key = await crypto.pbkdf2(password=password, salt="saltysalt", iterations=1003, length=16)
    return {"key": hex_key}


# ==============================================================================
# Cookie listing (raw, encrypted)
# ==============================================================================


@returns({"name": "string", "hostKey": "string", "path": "string", "encryptedValue": "string", "isSecure": "integer", "isHttponly": "integer", "expiresUtc": "integer"})
@connection("cookies_db")
async def list_cookies(*, domain, limit=1000, **kw):
    """List cookies for a domain with hex-encoded encrypted values."""
    db = COOKIES_DB
    return await sql.query("""
        SELECT name, host_key, path, hex(encrypted_value) as encrypted_value,
               is_secure, is_httponly, expires_utc, creation_utc
        FROM cookies
        WHERE host_key LIKE :domain
        ORDER BY name
        LIMIT :limit
    """, db=db, params={"domain": f"%{domain}%", "limit": limit})
