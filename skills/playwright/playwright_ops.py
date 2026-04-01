"""Playwright operations — thin Python wrapper around browser.ts via shell.run().

Each function maps a skill operation to a browser.ts command, passing params
as JSON on stdin and parsing JSON from stdout.
"""

import json
import os
from pathlib import Path

from agentos import shell

_SKILL_DIR = str(Path(__file__).parent)
_BROWSER_TS = "./scripts/browser.ts"

# Command name mapping: skill operation → browser.ts command
_CMD_MAP = {
    "read_webpage": "extract",
    "cookie_get": "cookies",
    "capture_network": "network_capture",
}


def _run(command: str, params: dict | None = None, timeout: float = 30.0) -> dict:
    """Run a browser.ts command with JSON params on stdin."""
    ts_cmd = _CMD_MAP.get(command, command)
    stdin_data = json.dumps(params or {})
    result = shell.run(
        "npx",
        ["tsx", _BROWSER_TS, ts_cmd],
        cwd=_SKILL_DIR,
        input=stdin_data,
        timeout=timeout,
    )
    if result.get("exit_code", 1) != 0:
        stderr = result.get("stderr", "")
        stdout = result.get("stdout", "")
        # Try to parse error from stdout (browser.ts returns JSON errors)
        if stdout:
            try:
                return json.loads(stdout)
            except json.JSONDecodeError:
                pass
        raise RuntimeError(f"playwright: {stderr or stdout or 'unknown error'}")
    stdout = result.get("stdout", "").strip()
    if not stdout:
        return {}
    return json.loads(stdout)


# --- Lifecycle ---

def start(mode: str = "headed", port: int = 9222, **_kw) -> dict:
    return _run("start", {"mode": mode, "port": port}, timeout=30)


def stop(port: int = 9222, **_kw) -> dict:
    return _run("stop", {"port": port}, timeout=10)


def status(port: int = 9222, **_kw) -> dict:
    return _run("status", {"port": port}, timeout=10)


# --- Navigation ---

def goto(url: str, wait_until: str = "load", **_kw) -> dict:
    return _run("goto", {"url": url, "wait_until": wait_until}, timeout=45)


def read_webpage(selector: str = "body", format: str = "text", **_kw) -> dict:
    return _run("read_webpage", {"selector": selector, "format": format}, timeout=30)


def url(**_kw) -> dict:
    return _run("url", timeout=10)


# --- Inspection ---

def inspect(selector: str = "body", **_kw) -> dict:
    return _run("inspect", {"selector": selector}, timeout=15)


def screenshot(
    selector: str | None = None,
    path: str = "/tmp/screenshot.png",
    full_page: bool = False,
    **_kw,
) -> dict:
    return _run(
        "screenshot",
        {"selector": selector, "path": path, "full_page": full_page},
        timeout=30,
    )


def errors(**_kw) -> dict:
    return _run("errors", timeout=30)


def evaluate(script: str, **_kw) -> dict:
    return _run("evaluate", {"script": script}, timeout=30)


# --- Interaction ---

def click(selector: str, **_kw) -> dict:
    return _run("click", {"selector": selector}, timeout=15)


def dblclick(selector: str, **_kw) -> dict:
    return _run("dblclick", {"selector": selector}, timeout=15)


def fill(selector: str, value: str, **_kw) -> dict:
    return _run("fill", {"selector": selector, "value": value}, timeout=15)


def select(selector: str, value: str, **_kw) -> dict:
    return _run("select", {"selector": selector, "value": value}, timeout=15)


def type(selector: str, text: str, **_kw) -> dict:
    return _run("type", {"selector": selector, "text": text}, timeout=30)


def wait(selector: str | None = None, timeout: int = 10000, **_kw) -> dict:
    return _run("wait", {"selector": selector, "timeout": timeout}, timeout=60)


# --- Tabs ---

def tabs(**_kw) -> dict:
    return _run("tabs", timeout=10)


def new_tab(url: str | None = None, **_kw) -> dict:
    return _run("new_tab", {"url": url}, timeout=30)


def close_tab(**_kw) -> dict:
    return _run("close_tab", timeout=10)


# --- Cookies ---

def cookie_get(domain: str, names: str | None = None, **_kw) -> dict:
    return _run("cookie_get", {"domain": domain, "names": names}, timeout=15)


def clear_cookies(domain: str, **_kw) -> dict:
    return _run("clear_cookies", {"domain": domain}, timeout=10)


# --- Network ---

def _header_to_playwright_cookies(cookie_header: str, domain: str) -> list[dict]:
    """Convert 'name=val; name2=val2' header string to Playwright cookie format."""
    cookies = []
    for part in cookie_header.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        name, _, value = part.partition("=")
        cookies.append({
            "name": name.strip(),
            "value": value.strip(),
            "domain": domain,
            "path": "/",
        })
    return cookies


def capture_network(
    url: str,
    pattern: str = "**",
    wait: int = 5000,
    cookies: list | None = None,
    cookie_domain: str | None = None,
    capture_body: bool = True,
    **_kw,
) -> dict:
    # Resolve cookies from auth system if cookie_domain provided
    if cookie_domain and not cookies:
        from agentos import http
        cookie_header = http.cookies(domain=cookie_domain)
        cookies = _header_to_playwright_cookies(cookie_header, cookie_domain)
    return _run(
        "capture_network",
        {
            "url": url,
            "pattern": pattern,
            "wait": wait,
            "cookies": cookies or [],
            "capture_body": capture_body,
        },
        timeout=60,
    )
