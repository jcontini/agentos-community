"""NSKeyedArchiver binary plist parsing through the engine.

    from agentos.macos import plist

    fields = plist.parse(hex_data, extract={"refresh_token": 32, "client_id": 13, "token_url": 10})
"""

from agentos._bridge import dispatch


def parse(hex_data, extract):
    """Parse an NSKeyedArchiver binary plist and extract fields.

    Args:
        hex_data: Hex-encoded binary plist data.
        extract: Dict mapping field names to NSKeyedArchiver object indices.

    Returns:
        Dict mapping field names to extracted string values.
    """
    return dispatch("__plist_parse__", {"hex_data": hex_data, "extract": extract})
