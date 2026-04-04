"""
get-cookie.py — Extract and decrypt cookies from Brave Browser on macOS.

Brave is Chromium-based: same cookie encryption as Chrome, different Keychain entry.

All I/O routes through the engine via SDK modules — no direct imports of
subprocess, sqlite3, or cryptography. This is important because the Python
sandbox blocks those imports. Every skill, including infrastructure skills
like cookie providers, must use SDK modules for I/O:

  keychain.read()   → engine __keychain_read__ → macOS Keychain
  crypto.pbkdf2()   → engine __crypto_pbkdf2__ → PBKDF2-HMAC-SHA1
  crypto.aes_decrypt() → engine __crypto_aes__ → AES-128-CBC
  sql.query()       → engine __sql_query__     → SQLite read

Chromium cookie encryption (v10):
  1. Master password stored in macOS Keychain ("Brave Safe Storage" / "Brave")
  2. Key derived via PBKDF2-HMAC-SHA1(password, "saltysalt", 1003 iterations, 16 bytes)
  3. Cookie values AES-128-CBC encrypted, IV = 16 space bytes (0x20)
  4. First 3 bytes are "v10" prefix, first 32 bytes of decrypted output are
     garbled (CBC IV mismatch artifact), real value starts at byte 32
"""

import os
import shutil
import tempfile

from agentos import sql, crypto
from agentos.macos import keychain


def get_master_key() -> str:
    """Read the Brave Safe Storage password from macOS Keychain.

    Returns the raw password string (not yet derived into an AES key).
    """
    return keychain.read(service="Brave Safe Storage", account="Brave")


def derive_key(password: str) -> str:
    """Derive AES-128 key using PBKDF2-HMAC-SHA1 (Chromium cookie encryption).

    Returns hex-encoded 16-byte key.
    """
    return crypto.pbkdf2(password=password, salt="saltysalt", iterations=1003, length=16)


def decrypt_cookie_value(encrypted_hex: str, key_hex: str) -> str | None:
    """Decrypt a Chromium v10 cookie value.

    encrypted_hex: hex-encoded bytes from the database (encrypted_value blob).
    key_hex: hex-encoded 16-byte AES key from derive_key().

    Chromium v10 encryption: AES-128-CBC with IV = 16 space bytes (0x20).
    The first 32 bytes of decrypted output are garbled (CBC IV mismatch artifact).
    The actual cookie value starts at byte 32.
    """
    raw = bytes.fromhex(encrypted_hex)
    if len(raw) < 4:
        return None

    prefix = raw[:3]
    if prefix != b"v10":
        # Not encrypted — might be plaintext
        try:
            return raw.decode("utf-8")
        except Exception:
            return None

    ciphertext = raw[3:]
    if len(ciphertext) == 0:
        return None

    # IV = 16 space bytes (0x20)
    iv_hex = "20" * 16

    try:
        plaintext_hex = crypto.aes_decrypt(key=key_hex, data=ciphertext.hex(), iv=iv_hex)
        plaintext = bytes.fromhex(plaintext_hex)
        # Skip first 32 bytes — garbled CBC IV mismatch artifact
        return plaintext[32:].decode("utf-8")
    except Exception:
        return None


def get_cookies(domain: str, names: list[str] | None = None,
                host: str | None = None, profile: str = "Default") -> list[dict]:
    """Extract and decrypt cookies for a domain from Brave's cookie DB."""
    cookies_db = os.path.expanduser(
        f"~/Library/Application Support/BraveSoftware/Brave-Browser/{profile}/Cookies"
    )
    if not os.path.exists(cookies_db):
        raise FileNotFoundError(f"Brave Cookies database not found: {cookies_db}")

    password = get_master_key()
    key_hex = derive_key(password)

    # Copy to temp to avoid lock conflicts with running Brave.
    # Also copy journal/WAL files so SQLite can replay uncommitted writes.
    tmp_dir = tempfile.mkdtemp()
    tmp_db = os.path.join(tmp_dir, "Cookies")
    shutil.copy2(cookies_db, tmp_db)
    for suffix in ("-journal", "-wal", "-shm"):
        aux = cookies_db + suffix
        if os.path.exists(aux):
            shutil.copy2(aux, tmp_db + suffix)

    try:
        # Always query by domain (broad TLD match) to get all cookies.
        # If host is specified, post-filter by RFC 6265 domain-matching.
        if names:
            placeholders = ",".join(f":name{i}" for i in range(len(names)))
            query = f"""
                SELECT name, host_key, path, hex(encrypted_value) AS encrypted_hex,
                       is_secure, is_httponly, expires_utc, creation_utc
                FROM cookies
                WHERE host_key LIKE :match
                  AND name IN ({placeholders})
                ORDER BY name
            """
            params = {"match": f"%{domain}%"}
            for i, n in enumerate(names):
                params[f"name{i}"] = n
        else:
            query = """
                SELECT name, host_key, path, hex(encrypted_value) AS encrypted_hex,
                       is_secure, is_httponly, expires_utc, creation_utc
                FROM cookies
                WHERE host_key LIKE :match
                ORDER BY name
            """
            params = {"match": f"%{domain}%"}

        rows = sql.query(query, db=tmp_db, params=params)

        cookies = []
        for row in rows:
            encrypted_hex = row.get("encrypted_hex", "")
            if not encrypted_hex:
                continue

            value = decrypt_cookie_value(encrypted_hex, key_hex)
            if value is None:
                continue

            expires_utc = row.get("expires_utc", 0) or 0
            if expires_utc > 0:
                expires_unix = (expires_utc / 1000000) - 11644473600
            else:
                expires_unix = -1

            creation_utc = row.get("creation_utc", 0) or 0
            if creation_utc > 0:
                created_unix = (creation_utc / 1000000) - 11644473600
            else:
                created_unix = -1

            cookies.append({
                "name": row["name"],
                "value": value,
                "domain": row["host_key"],
                "path": row["path"],
                "httpOnly": bool(row.get("is_httponly")),
                "secure": bool(row.get("is_secure")),
                "expires": expires_unix,
                "created": created_unix,
            })

        # RFC 6265 domain-matching: filter cookies to only those that should
        # be sent to the target host. Drops sibling subdomain cookies.
        if host:
            cookies = [c for c in cookies if _domain_matches(c["domain"], host)]

        return cookies
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _domain_matches(cookie_domain: str, request_host: str) -> bool:
    """RFC 6265 §5.1.3 domain matching.

    A cookie with domain=".uber.com" matches "riders.uber.com" (subdomain)
    and "uber.com" (exact). But domain=".auth.uber.com" does NOT match
    "riders.uber.com" (sibling subdomain).
    """
    cd = cookie_domain.lstrip(".")
    if request_host == cd:
        return True
    if request_host.endswith("." + cd):
        return True
    return False


def op_cookie_get(
    domain: str,
    names: str = None,
    host: str = None,
    profile: str = "Default",
) -> dict:
    """Extract and decrypt cookies — called by the python: executor with kwargs.

    `names` is a comma-separated string (matching the YAML param type: string).
    """
    names_list = [n.strip() for n in names.split(",") if n.strip()] if names else None
    profile = profile or "Default"
    cookies = get_cookies(domain, names_list, host=host or None, profile=profile)
    return {
        "domain": domain,
        "cookies": cookies,
        "count": len(cookies),
        "source": "brave",
        "profile": profile,
    }
