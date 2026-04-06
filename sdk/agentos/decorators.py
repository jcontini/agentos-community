"""Operation decorators — read by the engine via AST, no-ops at runtime.

The Rust engine parses Python files at boot time to discover operations.
These decorators exist so skills can import and use them without runtime errors.
The engine reads their arguments from the AST — it never executes Python.

Usage:
    from agentos import returns, provides, connection, timeout

    @returns("event[]")
    @provides(web_search, urls=["example.com/*"])
    @connection("api")
    @timeout(60)
    def list_events(query: str = None, **params) -> list[dict]:
        ...
"""


def returns(shape):
    """Declare the return shape of an operation.

    Args:
        shape: Entity shape reference ("event[]", "post") or inline schema dict
               ({"ok": "boolean", "id": "string"}).
    """
    def decorator(func):
        func._agentos_returns = shape
        return func
    return decorator


def provides(tool, **kwargs):
    """Declare that this function provides a standard tool capability.

    Args:
        tool: Tool constant (e.g., web_search, web_read, email_lookup).
        urls: Optional URL patterns this tool handles.
        domains: Optional domains (for cookie_auth providers).
        creation_timestamps: Whether provider returns cookie creation timestamps.
    """
    def decorator(func):
        func._agentos_provides = {"tool": tool, **kwargs}
        return func
    return decorator


def connection(name):
    """Bind this operation to a specific connection for auth resolution.

    Args:
        name: Connection name (e.g., "api", "web") or list of names
              (e.g., ["api", "cache"]) for caller-choosable connections.
    """
    def decorator(func):
        func._agentos_connection = name
        return func
    return decorator


def timeout(seconds):
    """Override the default 30-second timeout for this operation.

    Args:
        seconds: Timeout in seconds.
    """
    def decorator(func):
        func._agentos_timeout = seconds
        return func
    return decorator
