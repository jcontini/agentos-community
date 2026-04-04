"""Git skill — Python implementation replacing command: operations."""

import json
import re
from agentos import shell


def _git(*args, cwd=None):
    """Run a git command and return stdout. Raises on timeout or nonzero exit."""
    result = shell.run("git", list(args), cwd=cwd, timeout=30)
    if result["exit_code"] != 0:
        raise RuntimeError(result["stderr"].strip() or f"git exited {result['exit_code']}")
    return result["stdout"]


def _parse_shortstat(text):
    """Parse a --shortstat line into (files_changed, insertions, deletions)."""
    files = ins = dels = 0
    m = re.search(r"(\d+) files? changed", text)
    if m:
        files = int(m.group(1))
    m = re.search(r"(\d+) insertions?\(\+\)", text)
    if m:
        ins = int(m.group(1))
    m = re.search(r"(\d+) deletions?\(-\)", text)
    if m:
        dels = int(m.group(1))
    return files, ins, dels


_COMMIT_FORMAT = "%H%n%h%n%an%n%ae%n%cn%n%ce%n%aI%n%s"


def _parse_commit_block(block):
    """Parse an 8-line commit block (from _COMMIT_FORMAT) into a shape-native dict."""
    lines = block.strip().split("\n")
    if len(lines) < 8:
        return None
    sha = lines[0]
    author_name = lines[2]
    author_email = lines[3]
    committer_name = lines[4]
    committer_email = lines[5]
    return {
        "id": sha,
        "sha": sha,
        "shortHash": lines[1],
        "name": lines[7],
        "content": lines[7],
        "published": lines[6],
        "author": author_name,
        "committer": {
            "account": {
                "name": committer_name,
                "handle": committer_email,
                "platform": "email",
            }
        },
    }


def _commits_with_stats(raw):
    """Parse git log output that interleaves commit blocks and shortstat lines."""
    # Split on the COMMIT_SEP marker we injected
    chunks = raw.split("COMMIT_SEP\n")
    results = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        # The commit fields come first (8 lines), then optionally a blank line
        # and a shortstat line
        parts = chunk.split("\n")
        if len(parts) < 8:
            continue
        commit = _parse_commit_block("\n".join(parts[:8]))
        if not commit:
            continue
        # Look for shortstat in remaining lines
        files = ins = dels = 0
        for line in parts[8:]:
            if re.search(r"\d+ files? changed", line):
                files, ins, dels = _parse_shortstat(line)
                break
        commit["files_changed"] = files
        commit["additions"] = ins
        commit["deletions"] = dels
        results.append(commit)
    return results


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


def list_git_commits(path, limit=100, branch=None, author=None):
    """List recent commits in a git repository. Returns commits newest first with diff stats."""
    args = ["log"]
    if branch:
        args.append(branch)
    if author:
        args.extend(["--author", author])
    args.extend([
        f"-{limit}",
        f"--pretty=format:COMMIT_SEP%n{_COMMIT_FORMAT}",
        "--shortstat",
    ])
    raw = _git(*args, cwd=path)
    return _commits_with_stats(raw)


def get_git_commit(path, id):
    """Get a single commit with full details and diff stats."""
    raw = _git(
        "show", id,
        f"--pretty=format:{_COMMIT_FORMAT}",
        "--shortstat",
        cwd=path,
    )
    lines = raw.strip().split("\n")
    commit = _parse_commit_block("\n".join(lines[:8]))
    if not commit:
        raise RuntimeError(f"Could not parse commit {id}")
    files = ins = dels = 0
    for line in lines[8:]:
        if re.search(r"\d+ files? changed", line):
            files, ins, dels = _parse_shortstat(line)
            break
    commit["files_changed"] = files
    commit["additions"] = ins
    commit["deletions"] = dels
    return commit


def search_git_commits(path, query, limit=100):
    """Search commit messages by keyword."""
    args = [
        "log",
        f"--grep={query}",
        "-i",
        f"-{limit}",
        f"--pretty=format:COMMIT_SEP%n{_COMMIT_FORMAT}",
        "--shortstat",
    ]
    raw = _git(*args, cwd=path)
    return _commits_with_stats(raw)


def list_branches(path):
    """List all branches (local and remote) in a repository."""
    raw = _git(
        "branch", "-a",
        "--format=%(refname:short)|%(upstream:short)|%(HEAD)",
        cwd=path,
    )
    branches = []
    for line in raw.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|")
        name = parts[0] if len(parts) > 0 else ""
        upstream = parts[1] if len(parts) > 1 else ""
        head = parts[2] if len(parts) > 2 else ""
        branches.append({
            "id": name,
            "name": name,
            "upstream": upstream,
            "isRemote": name.startswith("origin/"),
            "isCurrent": head.strip() == "*",
        })
    return branches


def get_branch(path, name):
    """Get info about a specific branch."""
    raw = _git(
        "branch", "-a",
        "--format=%(refname:short)|%(upstream:short)|%(HEAD)",
        cwd=path,
    )
    for line in raw.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|")
        branch_name = parts[0] if len(parts) > 0 else ""
        if branch_name != name:
            continue
        upstream = parts[1] if len(parts) > 1 else ""
        head = parts[2] if len(parts) > 2 else ""
        return {
            "id": branch_name,
            "name": branch_name,
            "upstream": upstream,
            "isRemote": branch_name.startswith("origin/"),
            "isCurrent": head.strip() == "*",
        }
    raise RuntimeError(f"Branch not found: {name}")


def get_repository(path):
    """Get repository info from the local git repo -- remote URL, platform, branch."""
    try:
        remote = _git("remote", "get-url", "origin", cwd=path).strip()
    except RuntimeError:
        remote = ""

    try:
        branch = _git("branch", "--show-current", cwd=path).strip()
    except RuntimeError:
        branch = ""

    toplevel = _git("rev-parse", "--show-toplevel", cwd=path).strip()
    repo_name = toplevel.rsplit("/", 1)[-1]

    # Extract owner/repo from remote URL
    full_name = ""
    m = re.search(r"[:/]([^/]+/[^/.]+?)(?:\.git)?$", remote)
    if m:
        full_name = m.group(1)

    return {
        "id": full_name or repo_name,
        "name": repo_name,
        "url": remote,
        "defaultBranch": branch,
    }


def list_tags(path):
    """List all tags in the repository."""
    raw = _git(
        "tag", "-l",
        "--format=%(refname:short)|%(objectname:short)|%(creatordate:iso-strict)|%(subject)|%(objecttype)",
        cwd=path,
    )
    tags = []
    for line in raw.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|", 4)
        tag_name = parts[0] if len(parts) > 0 else ""
        tags.append({
            "id": tag_name,
            "name": tag_name,
            "hash": parts[1] if len(parts) > 1 else "",
            "published": parts[2] if len(parts) > 2 else "",
            "content": parts[3] if len(parts) > 3 else "",
            "annotated": (parts[4] == "tag") if len(parts) > 4 else False,
        })
    return tags


def get_tag(path, name):
    """Get info about a specific tag."""
    raw = _git(
        "tag", "-l", name,
        "--format=%(refname:short)|%(objectname:short)|%(creatordate:iso-strict)|%(subject)|%(objecttype)",
        cwd=path,
    )
    line = raw.strip().split("\n")[0] if raw.strip() else ""
    if not line:
        raise RuntimeError(f"Tag not found: {name}")
    parts = line.split("|", 4)
    tag_name = parts[0] if len(parts) > 0 else ""
    return {
        "id": tag_name,
        "name": tag_name,
        "hash": parts[1] if len(parts) > 1 else "",
        "published": parts[2] if len(parts) > 2 else "",
        "content": parts[3] if len(parts) > 3 else "",
        "annotated": (parts[4] == "tag") if len(parts) > 4 else False,
    }


def status(path):
    """Show working tree status -- modified, staged, and untracked files."""
    branch = _git("branch", "--show-current", cwd=path).strip()

    try:
        tracking = _git("rev-parse", "--abbrev-ref", "@{u}", cwd=path).strip()
    except RuntimeError:
        tracking = ""

    ahead = behind = 0
    if tracking:
        try:
            ahead = int(_git("rev-list", "--count", f"{tracking}..HEAD", cwd=path).strip())
        except (RuntimeError, ValueError):
            pass
        try:
            behind = int(_git("rev-list", "--count", f"HEAD..{tracking}", cwd=path).strip())
        except (RuntimeError, ValueError):
            pass

    staged_raw = _git("diff", "--cached", "--name-only", cwd=path).strip()
    staged = len(staged_raw.split("\n")) if staged_raw else 0

    modified_raw = _git("diff", "--name-only", cwd=path).strip()
    modified = len(modified_raw.split("\n")) if modified_raw else 0

    untracked_raw = _git("ls-files", "--others", "--exclude-standard", cwd=path).strip()
    untracked = len(untracked_raw.split("\n")) if untracked_raw else 0

    return {
        "branch": branch,
        "tracking": tracking,
        "ahead": ahead,
        "behind": behind,
        "staged": staged,
        "modified": modified,
        "untracked": untracked,
    }


def diff(path, staged=False, ref1=None, ref2=None):
    """Show the diff of working tree changes, staged changes, or between two refs."""
    args = ["diff"]
    if ref1:
        args.append(ref1)
        if ref2:
            args.append(ref2)
    elif staged:
        args.append("--cached")
    return _git(*args, cwd=path)


def log(path, format=None, limit=100, branch=None):
    """Raw git log output with flexible formatting."""
    args = ["log"]
    if branch:
        args.append(branch)
    args.extend([f"-{limit}", f"--format={format or 'oneline'}"])
    return _git(*args, cwd=path)
