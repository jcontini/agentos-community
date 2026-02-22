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

BASE_URL = "https://here.now/api/v1"


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

    # Read content from stdin if not provided as arg
    if args.content:
        content = args.content
    else:
        content = sys.stdin.read()

    content_bytes = content.encode("utf-8") if isinstance(content, str) else content
    token = args.token.strip() if args.token else ""
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

    # Step 1: Create or update publish — declare files and get presigned URLs
    create_body = {
        "files": [
            {
                "path": args.filename,
                "size": len(content_bytes),
                "contentType": args.content_type,
            }
        ]
    }

    if args.title or args.description:
        create_body["viewer"] = {}
        if args.title:
            create_body["viewer"]["title"] = args.title
        if args.description:
            create_body["viewer"]["description"] = args.description

    if args.ttl and token:
        create_body["ttlSeconds"] = args.ttl

    if args.slug:
        # Update existing publish
        url = f"{BASE_URL}/publish/{args.slug}"
        response = make_request(url, method="PUT", body=create_body, headers=dict(headers))
    else:
        # Create new publish
        url = f"{BASE_URL}/publish"
        response = make_request(url, method="POST", body=create_body, headers=dict(headers))

    slug = response.get("slug")
    site_url = response.get("siteUrl")
    upload_info = response.get("upload", {})
    uploads = upload_info.get("uploads", [])
    finalize_url = upload_info.get("finalizeUrl")
    version_id = upload_info.get("versionId")

    # Step 2: Upload each file to its presigned URL
    for upload in uploads:
        put_url = upload["url"]
        put_headers = dict(upload.get("headers", {}))
        make_request(put_url, method="PUT", body=content_bytes, headers=put_headers, content_type=args.content_type)

    # Step 3: Finalize — make it live
    finalize_headers = {}
    if token:
        finalize_headers["Authorization"] = f"Bearer {token}"
    make_request(finalize_url, method="POST", body={"versionId": version_id}, headers=finalize_headers)

    # Output raw here.now API format — the transformer maps this to the website entity.
    # Fields match what the transformer expects: slug, siteUrl, claimToken, claimUrl,
    # expiresAt, anonymous (we inject status and viewer.title manually below).
    output = {
        "slug": slug,
        "siteUrl": site_url,
        "status": "active",
        "currentVersionId": version_id,
    }

    if args.title:
        output["viewer"] = {"title": args.title}

    if response.get("expiresAt"):
        output["expiresAt"] = response["expiresAt"]

    if response.get("anonymous"):
        output["anonymous"] = True
        output["claimToken"] = response.get("claimToken", "")
        output["claimUrl"] = response.get("claimUrl", "")

    print(json.dumps(output))


if __name__ == "__main__":
    main()
