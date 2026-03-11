#!/usr/bin/env python3
"""
Extract and decrypt cookies from Brave Browser on macOS.

Usage:
    python3 get-cookie.py --host claude.ai --name sessionKey
    python3 get-cookie.py --host platform.claude.com --name sessionKey

Output:
    {"value": "sk-ant-..."}

How it works:
    1. Gets the master password from macOS Keychain ("Brave Safe Storage" / "Brave")
    2. Derives 16-byte AES key via PBKDF2-HMAC-SHA1 (salt="saltysalt", 1003 iterations)
    3. Copies the Cookies SQLite DB to /tmp (Brave may have it locked)
    4. Queries for the cookie's encrypted_value
    5. Decrypts: strips 3-byte "v10" prefix, AES-128-CBC with 16-space IV

Dependencies:
    - stdlib only + `cryptography` package
    - macOS only (uses `security` CLI for keychain access)
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


def get_master_key() -> bytes:
    """Read the Brave Safe Storage password from macOS Keychain."""
    result = subprocess.run(
        ["security", "find-generic-password", "-s", "Brave Safe Storage", "-a", "Brave", "-w"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Could not read Brave Safe Storage from Keychain: {result.stderr.strip()}"
        )
    password = result.stdout.strip()
    return password.encode("utf-8")


def derive_key(password: bytes) -> bytes:
    """Derive AES-128 key using PBKDF2-HMAC-SHA1 (Chromium cookie encryption)."""
    return hashlib.pbkdf2_hmac(
        hash_name="sha1",
        password=password,
        salt=b"saltysalt",
        iterations=1003,
        dklen=16,
    )


def decrypt_cookie(encrypted_value: bytes, key: bytes) -> str:
    """Decrypt a Chromium v10 cookie value using AES-128-CBC."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend

    # v10 prefix is 3 bytes — strip it
    prefix = encrypted_value[:3]
    if prefix != b"v10":
        raise ValueError(f"Unexpected cookie prefix: {prefix!r} (expected b'v10')")
    ciphertext = encrypted_value[3:]

    # IV is 16 space bytes (0x20)
    iv = b" " * 16

    cipher = Cipher(
        algorithms.AES(key),
        modes.CBC(iv),
        backend=default_backend(),
    )
    decryptor = cipher.decryptor()
    plaintext_padded = decryptor.update(ciphertext) + decryptor.finalize()

    # Remove PKCS7 padding
    pad_len = plaintext_padded[-1]
    plaintext = plaintext_padded[:-pad_len]

    # The first 32 bytes are two corrupted CBC blocks (IV mismatch artifact).
    # The actual token starts at offset 32.
    return plaintext[32:].decode("utf-8")


def get_cookie(host_pattern: str, cookie_name: str) -> bytes:
    """Copy Brave Cookies DB to /tmp and query for the cookie value."""
    cookies_db = os.path.expanduser(
        "~/Library/Application Support/BraveSoftware/Brave-Browser/Default/Cookies"
    )
    if not os.path.exists(cookies_db):
        raise FileNotFoundError(f"Brave Cookies database not found: {cookies_db}")

    # Copy to /tmp to avoid locking issues if Brave is running
    tmp_db = os.path.join(tempfile.gettempdir(), "brave-cookies-agentos.db")
    shutil.copy2(cookies_db, tmp_db)

    conn = sqlite3.connect(tmp_db)
    try:
        cursor = conn.execute(
            """
            SELECT encrypted_value
            FROM cookies
            WHERE host_key LIKE ?
              AND name = ?
            ORDER BY expires_utc DESC
            LIMIT 1
            """,
            (f"%{host_pattern}%", cookie_name),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(
                f"Cookie '{cookie_name}' not found for host pattern '%{host_pattern}%'"
            )
        return bytes(row[0])  # raw bytes from SQLite BLOB column
    finally:
        conn.close()
        try:
            os.unlink(tmp_db)
        except OSError:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract a cookie from Brave Browser on macOS"
    )
    parser.add_argument("--host", required=True, help="Host pattern (e.g. claude.ai or platform.claude.com)")
    parser.add_argument("--name", required=True, help="Cookie name (e.g. sessionKey)")
    args = parser.parse_args()

    try:
        password = get_master_key()
        key = derive_key(password)
        encrypted_value = get_cookie(args.host, args.name)
        value = decrypt_cookie(encrypted_value, key)
        print(json.dumps({"value": value}))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
