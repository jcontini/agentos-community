#!/usr/bin/env python3
"""
get-cookie.py — Extract and decrypt cookies from Brave Browser on macOS.

Brave is Chromium-based: same cookie encryption as Chrome, different Keychain entry.

Usage:
    python3 get-cookie.py --domain .claude.ai [--names sessionKey,csrf]
    python3 get-cookie.py --domain .chase.com --names JSESSIONID
    python3 get-cookie.py --domain .claude.ai --names sessionKey --host platform.claude.com

    Legacy (single cookie):
    python3 get-cookie.py --host platform.claude.com --name sessionKey

Output:
    JSON with { domain, cookies: [...], count, source }

How it works:
    1. Gets the master password from macOS Keychain ("Brave Safe Storage" / "Brave")
    2. Derives 16-byte AES key via PBKDF2-HMAC-SHA1 (salt="saltysalt", 1003 iterations)
    3. Copies the Cookies SQLite DB to /tmp (Brave may have it locked)
    4. Queries for cookies matching the domain
    5. Decrypts: strips 3-byte "v10" prefix, AES-128-CBC with 16-space IV, PKCS7 unpad
"""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as crypto_padding


def get_master_key() -> bytes:
    """Read the Brave Safe Storage password from macOS Keychain."""
    result = subprocess.run(
        ["security", "find-generic-password", "-s", "Brave Safe Storage", "-a", "Brave", "-w"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Could not read Brave Safe Storage from Keychain: {result.stderr.strip()}"
        )
    return result.stdout.strip().encode("utf-8")


def derive_key(password: bytes) -> bytes:
    """Derive AES-128 key using PBKDF2-HMAC-SHA1 (Chromium cookie encryption)."""
    return hashlib.pbkdf2_hmac("sha1", password, b"saltysalt", 1003, dklen=16)


def decrypt_cookie_value(encrypted_value: bytes, key: bytes) -> str | None:
    """Decrypt a Chromium v10 cookie value. Returns None on failure.

    Chromium v10 encryption: AES-128-CBC with IV = 16 space bytes.
    The first 32 bytes of decrypted output are garbled (CBC IV mismatch artifact).
    The actual cookie value starts at byte 32.
    """
    if len(encrypted_value) < 4:
        return None

    prefix = encrypted_value[:3]
    if prefix != b"v10":
        # Not encrypted — might be plaintext
        try:
            return encrypted_value.decode("utf-8")
        except Exception:
            return None

    ciphertext = encrypted_value[3:]
    if len(ciphertext) == 0:
        return None

    iv = b"\x20" * 16  # 16 space bytes

    try:
        cipher = Cipher(algorithms.AES128(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()

        unpadder = crypto_padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded) + unpadder.finalize()

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
    key = derive_key(password)

    # Copy to temp to avoid lock conflicts with running Brave
    tmp_dir = tempfile.mkdtemp()
    tmp_db = os.path.join(tmp_dir, "Cookies")
    shutil.copy2(cookies_db, tmp_db)

    try:
        conn = sqlite3.connect(tmp_db)
        conn.row_factory = sqlite3.Row

        # Use host if specified (more specific), otherwise use domain
        match_field = host or domain
        query = """
            SELECT name, host_key, path, encrypted_value,
                   is_secure, is_httponly, expires_utc
            FROM cookies
            WHERE host_key LIKE ?
        """
        params: list = [f"%{match_field}%"]

        if names:
            placeholders = ",".join("?" * len(names))
            query += f" AND name IN ({placeholders})"
            params.extend(names)

        query += " ORDER BY name"

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        cookies = []
        for row in rows:
            value = decrypt_cookie_value(bytes(row["encrypted_value"]), key)
            if value is None:
                continue

            expires_utc = row["expires_utc"]
            if expires_utc and expires_utc > 0:
                expires_unix = (expires_utc / 1000000) - 11644473600
            else:
                expires_unix = -1

            cookies.append({
                "name": row["name"],
                "value": value,
                "domain": row["host_key"],
                "path": row["path"],
                "httpOnly": bool(row["is_httponly"]),
                "secure": bool(row["is_secure"]),
                "expires": expires_unix,
            })

        return cookies
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


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


def main():
    parser = argparse.ArgumentParser(description="Extract decrypted cookies from Brave Browser")
    parser.add_argument("--domain", help="Cookie domain (e.g., .claude.ai, .chase.com)")
    parser.add_argument("--names", help="Comma-separated cookie names to filter")
    parser.add_argument("--host", help="Specific host_key to match (more specific than domain)")
    parser.add_argument("--name", help="Single cookie name (legacy, same as --names with one value)")
    parser.add_argument("--profile", default="Default", help="Brave profile (default: Default)")
    args = parser.parse_args()

    # Treat empty strings as None (template engine passes '' for unset params)
    if args.domain and not args.domain.strip():
        args.domain = None
    if args.names and not args.names.strip():
        args.names = None
    if args.host and not args.host.strip():
        args.host = None
    if args.name and not args.name.strip():
        args.name = None
    if args.profile and not args.profile.strip():
        args.profile = "Default"

    # Support legacy --host/--name single-cookie mode
    domain = args.domain or args.host
    if not domain:
        print(json.dumps({"error": "Either --domain or --host is required"}))
        sys.exit(1)

    names = None
    if args.names:
        names = [n.strip() for n in args.names.split(",") if n.strip()]
    elif args.name:
        names = [args.name]

    try:
        cookies = get_cookies(domain, names, host=args.host, profile=args.profile)

        # Legacy single-cookie mode: return { value: "..." }
        if args.name and not args.domain and len(cookies) > 0:
            print(json.dumps({"value": cookies[0]["value"]}))
            return

        print(json.dumps({
            "domain": domain,
            "cookies": cookies,
            "count": len(cookies),
            "source": "brave",
            "profile": args.profile,
        }))
    except FileNotFoundError as e:
        print(json.dumps({"error": str(e), "source": "brave"}))
        sys.exit(1)
    except RuntimeError as e:
        print(json.dumps({"error": str(e), "source": "brave"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
