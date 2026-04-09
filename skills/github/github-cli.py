#!/usr/bin/env python3
import base64
import json
import re
import sys
from agentos import shell, provides, returns, web_read


def _fail(message, code=1):
    print(json.dumps({"error": message}))
    sys.exit(code)


def _read_payload():
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


async def _run_gh(args):
    result = await shell.run("gh", list(args))
    if result["exit_code"] != 0:
        _fail(result["stderr"].strip() or result["stdout"].strip() or "gh command failed", result["exit_code"])
    return result["stdout"]


@returns("task[]")
async def list_tasks(*, repo, state="open", limit=30, **params):
    """List issues for a repository

        Args:
            repo: Repository in owner/name format
            state: open, closed, or all
            limit: Maximum number of issues to return
        """
    limit = str(limit)
    output = await _run_gh(["api", f"repos/{repo}/issues?state={state}&per_page={limit}"])
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
                "createdAt": item.get("created_at"),
                "updatedAt": item.get("updated_at"),
                "closedAt": item.get("closed_at"),
                "repository": repo,
                "labels": [label.get("name") for label in item.get("labels") or [] if label.get("name")],
                "author": ((item.get("user") or {}).get("login")),
            }
        )
    return result


def _parse_issue_or_pr_url(url: str) -> tuple[str, str] | None:
    """Return (owner/repo, number) for github.com/{owner}/{repo}/issues|pull/{n}."""
    m = re.search(
        r"github\.com/([^/]+)/([^/]+)/(?:issues|pull)/(\d+)(?:/|$|[?#])",
        url,
        re.I,
    )
    if not m:
        return None
    return f"{m.group(1)}/{m.group(2)}", str(m.group(3))


def _task_shape(item: dict, repo: str) -> dict:
    return {
        "number": item["number"],
        "title": item.get("title"),
        "body": item.get("body"),
        "url": item.get("html_url"),
        "state": item.get("state"),
        "createdAt": item.get("created_at"),
        "updatedAt": item.get("updated_at"),
        "closedAt": item.get("closed_at"),
        "repository": repo,
        "labels": [
            label.get("name")
            for label in item.get("labels") or []
            if label.get("name")
        ],
        "author": ((item.get("user") or {}).get("login")),
    }


@returns("task")
@provides(web_read, urls=["github.com/*/issues/*", "github.com/*/pull/*"])
async def get_task(*, repo=None, number=None, url=None, **params):
    """Get a single issue by number

        Args:
            repo: Repository in owner/name format — optional if url is a GitHub issue or PR link
            number: Issue or PR number — optional if url is set
            url: GitHub issue or pull request URL (web_read)
        """
    if url:
        parsed = _parse_issue_or_pr_url(url)
        if not parsed:
            _fail("Could not parse owner/repo and number from GitHub issue or PR URL")
        repo, number = parsed
    if not repo or number is None:
        _fail("repo and number are required (or pass url)")
    number = str(number)
    output = await _run_gh(["api", f"repos/{repo}/issues/{number}"])
    item = json.loads(output)
    if item.get("pull_request"):
        pr_out = await _run_gh(["api", f"repos/{repo}/pulls/{number}"])
        pr = json.loads(pr_out)
        return _task_shape(
            {
                "number": pr["number"],
                "title": pr.get("title"),
                "body": pr.get("body"),
                "htmlUrl": pr.get("html_url"),
                "state": pr.get("state"),
                "createdAt": pr.get("created_at"),
                "updatedAt": pr.get("updated_at"),
                "closedAt": pr.get("closed_at"),
                "labels": pr.get("labels") or [],
                "user": pr.get("user"),
            },
            repo,
        )
    return _task_shape(item, repo)


@returns({"url": "string", "number": "integer", "title": "string"})
async def create_task(*, repo, title, body="", **params):
    """Create a new GitHub issue

        Args:
            repo: Repository in owner/name format
            title: Issue title
            body: Issue body
        """
    url = await _run_gh(["issue", "create", "--repo", repo, "--title", title, "--body", body]).strip()
    return {"url": url, "number": int(url.rstrip("/").split("/")[-1]), "title": title}


@returns({"ok": "boolean", "url": "string"})
async def close_task(*, repo, number, **params):
    """Close an issue

        Args:
            number: Issue number
        """
    number = str(number)
    await _run_gh(["issue", "close", number, "--repo", repo])
    return {"ok": True, "url": f"https://github.com/{repo}/issues/{number}"}


@returns({"ok": "boolean", "url": "string"})
async def reopen_task(*, repo, number, **params):
    """Reopen a closed issue

        Args:
            number: Issue number
        """
    number = str(number)
    await _run_gh(["issue", "reopen", number, "--repo", repo])
    return {"ok": True, "url": f"https://github.com/{repo}/issues/{number}"}


@returns({"items": "array"})
async def list_pull_requests(*, repo, state="open", limit=30, **params):
    """List pull requests for a repository

        Args:
            repo: Repository in owner/name format
            state: open, closed, or all
            limit: Maximum number of pull requests to return
        """
    limit = str(limit)
    output = await _run_gh(
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


@returns({"url": "string"})
async def create_pull_request(*, repo, title, head, body="", base=None, **params):
    """Create a pull request

        Args:
            repo: Repository in owner/name format
            title: Pull request title
            body: Pull request body
            head: Source branch
            base: Target branch
        """
    args = [
        "pr",
        "create",
        "--repo",
        repo,
        "--title",
        title,
        "--body",
        body,
        "--head",
        head,
    ]
    if base:
        args.extend(["--base", base])
    url = await _run_gh(args).strip()
    return {"url": url}


def _contents_endpoint(repo, path=None, ref=None):
    endpoint = f"repos/{repo}/contents"
    path_part = (path or "").strip("/")
    if path_part:
      endpoint = f"{endpoint}/{path_part}"
    if ref:
      endpoint = f"{endpoint}?ref={ref}"
    return endpoint


@returns("file[]")
async def list_documents(*, repo, path=None, ref=None, **params):
    """List files and folders at a repository path

        Args:
            repo: Repository in owner/name format
            path: Path within the repository
            ref: Branch, tag, or commit
        """
    endpoint = _contents_endpoint(repo, path, ref)
    output = await _run_gh(["api", endpoint])
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
                "repository": repo,
            }
        )
    return result


def _parse_blob_or_raw_url(url: str) -> tuple[str, str, str] | None:
    """
    Return (owner/repo, path, ref) for blob or raw.githubusercontent.com URLs.
    """
    m = re.search(
        r"github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+?)(?:[?#]|$)",
        url,
        re.I,
    )
    if m:
        return f"{m.group(1)}/{m.group(2)}", m.group(4), m.group(3)
    m = re.search(
        r"raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+?)(?:[?#]|$)",
        url,
        re.I,
    )
    if m:
        return f"{m.group(1)}/{m.group(2)}", m.group(4), m.group(3)
    return None


@returns("file")
@provides(web_read, urls=["github.com/*/blob/*", "raw.githubusercontent.com/*"])
async def read_document(*, repo=None, path=None, ref=None, url=None, **params):
    """Read a text file from a repository

        Args:
            repo: Repository in owner/name format — optional if url is a blob or raw.githubusercontent.com link
            path: File path within the repository — optional if url is set
            ref: Branch, tag, or commit — optional if url is set
            url: GitHub blob URL or raw.githubusercontent.com file URL (web_read)
        """
    if url:
        parsed = _parse_blob_or_raw_url(url)
        if not parsed:
            _fail("Could not parse GitHub blob or raw.githubusercontent.com URL")
        repo, path, ref = parsed
    if not repo or not path:
        _fail("repo and path are required (or pass url)")
    endpoint = _contents_endpoint(repo, path, ref)
    output = await _run_gh(["api", endpoint])
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
        "repository": repo,
        "content": content,
    }


@returns({"output": "string"})
async def status(**params):
    """Show GitHub CLI status for the current machine"""
    output = await _run_gh(["status"])
    return {"output": output}


def _main():
    if len(sys.argv) < 2:
        _fail("Missing operation")
    operation = sys.argv[1]
    payload = _read_payload()
    params = (payload.get("params") or {})
    operations = {
        "listTasks": list_tasks,
        "getTask": get_task,
        "createTask": create_task,
        "closeTask": close_task,
        "reopenTask": reopen_task,
        "listPullRequests": list_pull_requests,
        "createPullRequest": create_pull_request,
        "listDocuments": list_documents,
        "readDocument": read_document,
        "status": status,
    }
    handler = operations.get(operation)
    if not handler:
        _fail(f"Unknown operation: {operation}")
    print(json.dumps(handler(**params)))


if __name__ == "__main__":
    _main()
