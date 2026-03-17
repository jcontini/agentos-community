#!/usr/bin/env python3
import base64
import json
import subprocess
import sys


def fail(message, code=1):
    print(json.dumps({"error": message}))
    sys.exit(code)


def read_payload():
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


def run_gh(args):
    proc = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        fail(proc.stderr.strip() or proc.stdout.strip() or "gh command failed", proc.returncode)
    return proc.stdout


def list_tasks(params):
    repo = params["repo"]
    state = params.get("state", "open")
    limit = str(params.get("limit", 30))
    output = run_gh(["api", f"repos/{repo}/issues?state={state}&per_page={limit}"])
    data = json.loads(output)
    result = []
    for item in data:
        if item.get("pull_request"):
            continue
        result.append(
            {
                "number": item["number"],
                "title": item.get("title"),
                "body": item.get("body"),
                "url": item.get("html_url"),
                "state": item.get("state"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "closed_at": item.get("closed_at"),
                "repository": repo,
                "labels": [label.get("name") for label in item.get("labels") or [] if label.get("name")],
                "author": ((item.get("user") or {}).get("login")),
            }
        )
    return result


def get_task(params):
    repo = params["repo"]
    number = str(params["number"])
    output = run_gh(["api", f"repos/{repo}/issues/{number}"])
    item = json.loads(output)
    if item.get("pull_request"):
        fail(f"{repo}#{number} is a pull request, not an issue")
    return {
        "number": item["number"],
        "title": item.get("title"),
        "body": item.get("body"),
        "url": item.get("html_url"),
        "state": item.get("state"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "closed_at": item.get("closed_at"),
        "repository": repo,
        "labels": [label.get("name") for label in item.get("labels") or [] if label.get("name")],
        "author": ((item.get("user") or {}).get("login")),
    }


def create_task(params):
    repo = params["repo"]
    title = params["title"]
    body = params.get("body", "")
    url = run_gh(["issue", "create", "--repo", repo, "--title", title, "--body", body]).strip()
    return {"url": url, "number": int(url.rstrip("/").split("/")[-1]), "title": title}


def close_task(params):
    repo = params["repo"]
    number = str(params["number"])
    run_gh(["issue", "close", number, "--repo", repo])
    return {"ok": True, "url": f"https://github.com/{repo}/issues/{number}"}


def reopen_task(params):
    repo = params["repo"]
    number = str(params["number"])
    run_gh(["issue", "reopen", number, "--repo", repo])
    return {"ok": True, "url": f"https://github.com/{repo}/issues/{number}"}


def list_pull_requests(params):
    repo = params["repo"]
    state = params.get("state", "open")
    limit = str(params.get("limit", 30))
    output = run_gh(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            state,
            "--limit",
            limit,
            "--json",
            "number,title,url,state,headRefName,baseRefName,createdAt,updatedAt,author",
        ]
    )
    return json.loads(output)


def create_pull_request(params):
    repo = params["repo"]
    args = [
        "pr",
        "create",
        "--repo",
        repo,
        "--title",
        params["title"],
        "--body",
        params.get("body", ""),
        "--head",
        params["head"],
    ]
    if params.get("base"):
        args.extend(["--base", params["base"]])
    url = run_gh(args).strip()
    return {"url": url}


def contents_endpoint(params):
    endpoint = f"repos/{params['repo']}/contents"
    path_part = params.get("path", "").strip("/")
    if path_part:
      endpoint = f"{endpoint}/{path_part}"
    if params.get("ref"):
      endpoint = f"{endpoint}?ref={params['ref']}"
    return endpoint


def list_documents(params):
    endpoint = contents_endpoint(params)
    output = run_gh(["api", endpoint])
    data = json.loads(output)
    items = data if isinstance(data, list) else [data]
    result = []
    for item in items:
        result.append(
            {
                "sha": item.get("sha") or item.get("path"),
                "path": item.get("path"),
                "name": item.get("name"),
                "url": item.get("html_url"),
                "size": item.get("size"),
                "kind": item.get("type"),
                "repository": params["repo"],
            }
        )
    return result


def read_document(params):
    endpoint = contents_endpoint(params)
    output = run_gh(["api", endpoint])
    data = json.loads(output)
    content = data.get("content")
    if content is not None:
        content = base64.b64decode(content.encode("utf-8")).decode("utf-8", errors="replace")
    return {
        "sha": data.get("sha"),
        "path": data.get("path"),
        "name": data.get("name"),
        "url": data.get("html_url"),
        "size": data.get("size"),
        "kind": data.get("type"),
        "repository": params["repo"],
        "content": content,
    }


def status(params=None):
    output = run_gh(["status"])
    return {"output": output}


def main():
    if len(sys.argv) < 2:
        fail("Missing operation")
    operation = sys.argv[1]
    params = (read_payload().get("params") or {})
    operations = {
        "list_tasks": list_tasks,
        "get_task": get_task,
        "create_task": create_task,
        "close_task": close_task,
        "reopen_task": reopen_task,
        "list_pull_requests": list_pull_requests,
        "create_pull_request": create_pull_request,
        "list_documents": list_documents,
        "read_document": read_document,
        "status": status,
    }
    handler = operations.get(operation)
    if not handler:
        fail(f"Unknown operation: {operation}")
    print(json.dumps(handler(params)))


if __name__ == "__main__":
    main()
