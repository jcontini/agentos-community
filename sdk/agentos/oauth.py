"""OAuth token exchange through the engine.

Sugar over http.post() with standard OAuth2 form body.

    from agentos import oauth

    token = oauth.exchange(
        token_url="https://oauth2.googleapis.com/token",
        refresh_token="...",
        client_id="...",
    )
    # token["access_token"] — the Bearer token
    # token["scope"] — space-separated granted scopes (if returned by provider)

## How the engine returns HTTP responses

The engine's __http_request__ dispatch returns:
    {"status": int, "ok": bool, "body": "<raw text>", "json": <parsed dict or null>, ...}

IMPORTANT: "body" is always the raw text string. "json" is the parsed dict.
Always read "json" for structured data. This was the source of a silent auth
failure (2026-04-02): oauth.exchange read "body" (a string), failed the
isinstance(body, dict) check, and returned the wrapper — causing every
downstream credential_get to return access_token=None.
"""

from agentos._bridge import dispatch


def exchange(token_url, refresh_token, client_id, client_secret=None, scope=None):
    """Exchange a refresh token for an access token.

    Args:
        token_url: OAuth2 token endpoint URL.
        refresh_token: The refresh token.
        client_id: OAuth2 client ID.
        client_secret: Optional client secret.
        scope: Optional scope string.

    Returns:
        Dict with access_token, expires_in, token_type, scope, etc.
        The "scope" field (space-separated string) tells you what permissions
        the token actually has — persist this for introspection.
    """
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }
    if client_secret:
        data["client_secret"] = client_secret
    if scope:
        data["scope"] = scope

    result = dispatch("__http_request__", {
        "method": "POST",
        "url": token_url,
        "data": data,
    })

    # Engine returns {status, ok, body (raw text), json (parsed dict), ...}
    # ALWAYS read "json" for structured data, never "body" (which is a string).
    if isinstance(result, dict):
        parsed = result.get("json")
        if isinstance(parsed, dict):
            # Check for OAuth error responses (e.g. invalid_grant)
            if "error" in parsed:
                raise RuntimeError(
                    f"OAuth token exchange failed: {parsed.get('error')} "
                    f"— {parsed.get('error_description', 'no description')}"
                )
            return parsed
    return result
