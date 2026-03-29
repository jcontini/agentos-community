#!/usr/bin/env python3
"""
here.now publish script

Handles the full 3-step publish flow:
  1. POST /api/v1/publish    — declare files, get presigned upload URLs
  2. PUT <presigned-url>     — upload each file
  3. POST <finalizeUrl>      — go live

Returns a JSON object matching the website entity schema.

Usage:
  python3 publish.py --filename index.html --content-type "text/html; charset=utf-8" [--title "My Site"] [--token <api-key>] [--slug <existing-slug>]
  echo "<html>...</html>" | python3 publish.py --filename index.html

For updates (redeploy), pass --slug to target an existing publish.
For anonymous publishes (no --token), the response includes claim_token and claim_url — surfaced in data so the agent can show them to the user.
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error

from agentos import surf

BASE_URL = "https://here.now/api/v1"


def _map_website(w: dict) -> dict:
    viewer = w.get("viewer") or {}
    return {
        "id": w.get("slug"),
        "name": viewer.get("title") or w.get("slug"),
        "url": w.get("siteUrl"),
        "status": "active" if w.get("status") == "active" else "pending",
        "datePublished": w.get("updatedAt"),
        "version_id": w.get("currentVersionId"),
        "expires_at": w.get("expiresAt"),
        "anonymous": w.get("anonymous", False),
        "claim_token": w.get("claimToken"),
        "claim_url": w.get("claimUrl"),
    }


def list_websites(**params) -> list[dict]:
    token = params.get("auth", {}).get("key", "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with surf(profile="api") as client:
        resp = client.get(f"{BASE_URL}/publishes", headers=headers)
        resp.raise_for_status()
    return [_map_website(w) for w in resp.json().get("publishes", [])]


def delete_website(*, slug: str, **params) -> dict:
    token = params.get("auth", {}).get("key", "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with surf(profile="api") as client:
        resp = client.delete(f"{BASE_URL}/publish/{slug}", headers=headers)
        resp.raise_for_status()
    return {"success": True, "id": slug}


def claim_website(*, slug: str, claim_token: str, **params) -> dict:
    token = params.get("auth", {}).get("key", "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with surf(profile="api") as client:
        resp = client.post(
            f"{BASE_URL}/publish/{slug}/claim",
            json={"claimToken": claim_token},
            headers=headers,
        )
        resp.raise_for_status()
    return {"success": True, "slug": slug}


def op_signup(*, email: str, **params) -> dict:
    with surf(profile="api") as client:
        resp = client.post("https://here.now/api/auth/login", json={"email": email})
        resp.raise_for_status()
    return {
        "sent": True,
        "message": (
            "Check your inbox for a sign-in link from here.now. "
            "Click it, then copy your API key from the dashboard "
            "and add it to AgentOS credentials for this skill."
        ),
    }


def patch_metadata(*, slug: str, title: str = None, description: str = None, ttl: int = None, **params) -> dict:
    token = params.get("auth", {}).get("key", "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    body: dict = {}
    if ttl is not None:
        body["ttlSeconds"] = ttl
    viewer: dict = {}
    if title:
        viewer["title"] = title
    if description:
        viewer["description"] = description
    if viewer:
        body["viewer"] = viewer
    with surf(profile="api") as client:
        resp = client.patch(
            f"{BASE_URL}/publish/{slug}/metadata",
            json=body,
            headers=headers,
        )
        resp.raise_for_status()
    return {"success": True}


def make_request(url, method="GET", body=None, headers=None, content_type="application/json"):
    headers = headers or {}
    if body is not None and "Content-Type" not in headers:
        headers["Content-Type"] = content_type

    data = None
    if body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body).encode("utf-8")
        elif isinstance(body, str):
            data = body.encode("utf-8")
        else:
            data = body

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            try:
                return json.loads(raw)
            except Exception:
                return raw.decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            err = json.loads(body)
        except Exception:
            err = {"error": body}
        print(json.dumps({"success": False, "error": str(e), "detail": err}), file=sys.stderr)
        sys.exit(1)


def do_publish(
    content,
    filename="index.html",
    content_type="text/html; charset=utf-8",
    title=None,
    description=None,
    slug=None,
    token=None,
    ttl=None,
):
    """Core publish logic. Content can be str or bytes. Returns website entity dict."""
    content_bytes = content.encode("utf-8") if isinstance(content, str) else content
    token = (token or "").strip()
    if not token:
        creds_path = os.path.expanduser("~/.herenow/credentials")
        try:
            with open(creds_path) as f:
                token = f.read().strip()
        except FileNotFoundError:
            pass

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    create_body = {
        "files": [
            {
                "path": filename,
                "size": len(content_bytes),
                "contentType": content_type,
            }
        ]
    }

    if title or description:
        create_body["viewer"] = {}
        if title:
            create_body["viewer"]["title"] = title
        if description:
            create_body["viewer"]["description"] = description

    if ttl and token:
        create_body["ttlSeconds"] = ttl

    if slug:
        url = f"{BASE_URL}/publish/{slug}"
        response = make_request(url, method="PUT", body=create_body, headers=dict(headers))
    else:
        url = f"{BASE_URL}/publish"
        response = make_request(url, method="POST", body=create_body, headers=dict(headers))

    slug_val = response.get("slug")
    site_url = response.get("siteUrl")
    upload_info = response.get("upload", {})
    uploads = upload_info.get("uploads", [])
    finalize_url = upload_info.get("finalizeUrl")
    version_id = upload_info.get("versionId")

    for upload in uploads:
        put_url = upload["url"]
        put_headers = dict(upload.get("headers", {}))
        make_request(put_url, method="PUT", body=content_bytes, headers=put_headers, content_type=content_type)

    finalize_headers = {}
    if token:
        finalize_headers["Authorization"] = f"Bearer {token}"
    make_request(finalize_url, method="POST", body={"versionId": version_id}, headers=finalize_headers)

    output = {
        "slug": slug_val,
        "siteUrl": site_url,
        "status": "active",
        "currentVersionId": version_id,
    }
    if title:
        output["viewer"] = {"title": title}
    if response.get("expiresAt"):
        output["expiresAt"] = response["expiresAt"]
    if response.get("anonymous"):
        output["anonymous"] = True
        output["claimToken"] = response.get("claimToken", "")
        output["claimUrl"] = response.get("claimUrl", "")

    return output


def op_create_website(
    content,
    filename="index.html",
    content_type="text/html; charset=utf-8",
    title=None,
    description=None,
    ttl=None,
    **params,
):
    """Entry point for python: executor. Create a new publish."""
    token = params.get("auth", {}).get("key", "")
    return do_publish(
        content=content,
        filename=filename,
        content_type=content_type,
        title=title,
        description=description,
        ttl=ttl,
        token=token,
    )


def op_update_website(
    slug,
    content,
    filename="index.html",
    content_type="text/html; charset=utf-8",
    title=None,
    **params,
):
    """Entry point for python: executor. Update an existing publish."""
    token = params.get("auth", {}).get("key", "")
    return do_publish(
        content=content,
        filename=filename,
        content_type=content_type,
        title=title,
        slug=slug,
        token=token,
    )


def main():
    parser = argparse.ArgumentParser(description="Publish files to here.now")
    parser.add_argument("--filename", default="index.html", help="File path within the publish")
    parser.add_argument("--content-type", default="text/html; charset=utf-8", dest="content_type")
    parser.add_argument("--content", help="File content (reads from stdin if omitted)")
    parser.add_argument("--title", help="Human-readable site title")
    parser.add_argument("--description", help="Site description")
    parser.add_argument("--ttl", type=int, help="TTL in seconds (authenticated only)")
    parser.add_argument("--token", default="", help="here.now API key (omit for anonymous)")
    parser.add_argument("--slug", help="Existing slug to update (omit to create new)")
    args = parser.parse_args()

    content = args.content if args.content else sys.stdin.read()
    output = do_publish(
        content=content,
        filename=args.filename,
        content_type=args.content_type,
        title=args.title,
        description=args.description,
        slug=args.slug,
        token=args.token or "",
        ttl=args.ttl,
    )
    print(json.dumps(output))


if __name__ == "__main__":
    main()
