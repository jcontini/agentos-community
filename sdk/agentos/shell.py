"""Controlled binary execution — routes through engine via __exec__.

Every subprocess call goes through the engine, which logs the invocation
and enforces allowlists. Shell interpreters (bash, sh, zsh) are always blocked.

    from agentos import shell

    result = shell.run("git", ["log", "--oneline", "-5"], cwd="/path/to/repo")
    print(result["stdout"])
"""

from agentos._bridge import dispatch


def run(
    binary: str,
    args: list[str] | None = None,
    *,
    cwd: str | None = None,
    input: str | None = None,
    timeout: float = 30.0,
) -> dict:
    """Run a binary with arguments. Returns dict with exit_code, stdout, stderr.

    The engine blocks shell interpreters and logs every invocation.
    """
    params = {"binary": binary, "args": args or [], "timeout": timeout}
    if cwd:
        params["cwd"] = cwd
    if input is not None:
        params["input"] = input
    return dispatch("__exec__", params)
