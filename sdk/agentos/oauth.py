"""OAuth token exchange through the engine.

Sugar over http.post() with standard OAuth2 form body.

    from agentos import oauth

    token = oauth.exchange(
        token_url="https://oauth2.googleapis.com/token",
        refresh_token="...",
        client_id="...",
    )
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
        Dict with access_token, expires_in, token_type, etc.
    """
    # OAuth exchange is just an HTTP POST with form data
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

    # The HTTP response wraps the OAuth response in {status, headers, body}
    if isinstance(result, dict) and "body" in result:
        body = result["body"]
        if isinstance(body, dict):
            return body
        return result
    return result
