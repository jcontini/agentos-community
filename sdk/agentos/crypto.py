"""Cryptographic operations through the engine.

Used by browser cookie decryption (Brave, Chrome, Edge all use PBKDF2 + AES).

    from agentos import crypto

    key = crypto.pbkdf2(password="pass", salt="saltysalt", iterations=1003, length=16)
    plaintext = crypto.aes_decrypt(key=key, data=encrypted_hex)
"""

from agentos._bridge import dispatch


def pbkdf2(password, salt, iterations=1, length=16):
    """Derive a key using PBKDF2-HMAC-SHA1.

    Args:
        password: Password string.
        salt: Salt string.
        iterations: Number of iterations.
        length: Desired key length in bytes.

    Returns:
        Hex-encoded derived key string.
    """
    result = dispatch("__crypto_pbkdf2__", {
        "password": password,
        "salt": salt,
        "iterations": iterations,
        "length": length,
    })
    return result.get("key_hex", result)


def aes_decrypt(key, data, iv=None, mode="cbc"):
    """Decrypt data using AES-128-CBC.

    Args:
        key: Hex-encoded 16-byte key.
        data: Hex-encoded ciphertext.
        iv: Hex-encoded 16-byte IV (defaults to zeros).
        mode: Only 'cbc' supported currently.

    Returns:
        Hex-encoded plaintext.
    """
    params = {"key": key, "data": data}
    if iv:
        params["iv"] = iv
    result = dispatch("__crypto_aes__", params)
    return result.get("plaintext_hex", result)
