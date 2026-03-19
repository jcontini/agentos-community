"""Gmail operations that compose REST stubs into full results via _call dispatch."""


def list_emails(query="", limit=20, label_ids=None, page_token=None, _call=None):
    """List emails with full content (subject, snippet, headers, body).

    Calls list_email_stubs to get IDs, then get_email per stub.
    """
    params = {"limit": limit}
    if query:
        params["query"] = query
    if label_ids:
        params["label_ids"] = label_ids
    if page_token:
        params["page_token"] = page_token

    stubs = _call("list_email_stubs", params)
    if not stubs:
        return []
    return [_call("get_email", {"id": s["id"]}) for s in stubs]


def search_emails(query, limit=20, _call=None):
    """Search emails with full content using Gmail query syntax.

    Calls list_email_stubs with the query, then get_email per stub.
    """
    stubs = _call("list_email_stubs", {"query": query, "limit": limit})
    if not stubs:
        return []
    return [_call("get_email", {"id": s["id"]}) for s in stubs]
