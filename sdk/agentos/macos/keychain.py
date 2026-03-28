"""macOS Keychain access through the engine.

    from agentos.macos import keychain

    password = keychain.read(service="MyApp", account="user@example.com")
    raw = keychain.read(service="Mimestream: joe@co", account="OAuth", binary=True)
"""

from agentos._bridge import dispatch


def read(service, account=None, binary=False):
    """Read a value from the macOS Keychain.

    Args:
        service: Keychain service name.
        account: Optional account name.
        binary: If True, return hex-encoded binary data (for NSKeyedArchiver plists).

    Returns:
        The secret string (or hex-encoded binary if binary=True).
    """
    params = {"service": service, "binary": binary}
    if account:
        params["account"] = account
    result = dispatch("__keychain_read__", params)
    return result.get("value", result) if isinstance(result, dict) else result
