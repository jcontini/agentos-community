"""Engine dispatch bridge — invisible to skill authors.

The engine loader injects the actual dispatch function into `_dispatch`
before the skill function runs. SDK modules call `dispatch(op, params)`
which routes through the engine for logging, firewall, and execution.

Skill authors never import this module directly. They use:
    from agentos import sql, http, crypto, oauth
    from agentos.macos import keychain, plist
"""

_dispatch = None  # Set by engine loader before skill function runs


def dispatch(op, params):
    """Send a dispatch request to the engine, return result.

    Args:
        op: Operation name (e.g. '__sql_query__', '__http_request__').
        params: Dict of operation parameters.

    Returns:
        The engine's response (parsed JSON).

    Raises:
        RuntimeError: If called outside engine context (no dispatch injected).
        RuntimeError: If the engine returns an error.
    """
    if _dispatch is None:
        raise RuntimeError(
            "agentos SDK called outside of engine context. "
            "SDK modules can only be used inside skill functions executed by the engine."
        )
    result = _dispatch(op, params)
    if isinstance(result, dict) and "__error__" in result:
        raise RuntimeError(f"Engine dispatch '{op}' failed: {result['__error__']}")
    return result
