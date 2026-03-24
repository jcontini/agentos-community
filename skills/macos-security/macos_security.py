"""
macOS Security skill — Keychain audit, token extraction, OAuth app scanning.

All operations run locally against the macOS Keychain and /Applications.
No network calls. Requires macOS.
"""

import json
import os
import re
import subprocess
from pathlib import Path


# ── Helpers ───────────────────────────────────────────────────────────────────

def _security(*args) -> str:
    """Run a `security` CLI command, return stdout."""
    result = subprocess.run(
        ["security"] + list(args),
        capture_output=True, text=True
    )
    return result.stdout.strip()


def _dump_keychain() -> str:
    return _security("dump-keychain")


def _parse_keychain_entries(dump: str) -> list[dict]:
    """
    Parse `security dump-keychain` output into structured entries.
    Each Keychain item spans multiple lines; we group by blank-line separator.
    """
    entries = []
    current: dict = {}

    for line in dump.splitlines():
        # New item starts with a line like: keychain: "/Users/.../login.keychain-db"
        if line.startswith("keychain:"):
            if current:
                entries.append(current)
            current = {}
            continue

        # Parse tagged fields like:    "svce"<blob>="Cursor Safe Storage"
        m = re.search(r'"(\w+)"<\w+>="([^"]*)"', line)
        if m:
            current[m.group(1)] = m.group(2)
            continue

        # Handle NULL values:    "svce"<blob>=<NULL>
        m = re.search(r'"(\w+)"<\w+>=<NULL>', line)
        if m:
            current[m.group(1)] = None

    if current:
        entries.append(current)

    return entries


_APPLE_NOISE = re.compile(
    r"apple|icloud|cloudkit|webkit|safari|xpc|nsurl|networkservice|"
    r"airportd|mobileMe|ani-|com\.apple\.|bluetooth|certificate",
    re.IGNORECASE,
)

def _is_interesting(entry: dict) -> bool:
    svce = entry.get("svce") or ""
    acct = entry.get("acct") or ""
    combined = svce + acct
    return not _APPLE_NOISE.search(combined)


_SAFE_STORAGE = re.compile(r"^(.+) Safe Storage$")
_MIMESTREAM   = re.compile(r"^Mimestream: (.+)$")
_GH_CLI       = re.compile(r"^gh:(.+)$")
_CURSOR_TOK   = re.compile(r"^cursor-(access|refresh)-token$")

def _categorize(entry: dict) -> str | None:
    svce = entry.get("svce") or ""
    acct = entry.get("acct") or ""

    if _SAFE_STORAGE.match(svce):
        return "electron_safe_storage"
    if _MIMESTREAM.match(svce) and acct == "OAuth":
        return "google_oauth_native"
    if _GH_CLI.match(svce):
        return "github_cli"
    if _CURSOR_TOK.match(svce):
        return "cursor_token"
    if re.search(r"token|oauth|refresh|access_tok", svce + acct, re.IGNORECASE):
        return "app_token"
    if re.search(r"key|secret|credential|password|api", svce + acct, re.IGNORECASE):
        return "api_key_or_secret"
    return "other"


# ── Operations ────────────────────────────────────────────────────────────────

def cmd_audit(**kwargs) -> list[dict]:
    """
    Full credential inventory. Returns categorized entries sorted by category.
    """
    dump = _dump_keychain()
    raw_entries = _parse_keychain_entries(dump)
    interesting = [e for e in raw_entries if _is_interesting(e)]

    results = []
    for entry in interesting:
        category = _categorize(entry)
        if category is None:
            continue

        svce = entry.get("svce") or ""
        acct = entry.get("acct") or ""

        item: dict = {"category": category}

        if category == "electron_safe_storage":
            m = _SAFE_STORAGE.match(svce)
            item["app"] = m.group(1) if m else svce
            item["note"] = "Master encryption key for all locally stored credentials"
            app_support = Path.home() / "Library" / "Application Support" / item["app"]
            if app_support.exists():
                item["data_path"] = str(app_support)

        elif category == "google_oauth_native":
            m = _MIMESTREAM.match(svce)
            item["app"] = "Mimestream"
            item["account"] = m.group(1) if m else acct
            item["service_name"] = svce
            item["account_name"] = acct
            item["note"] = "Google OAuth tokens (Gmail, Calendar, Contacts scopes)"

        elif category == "github_cli":
            m = _GH_CLI.match(svce)
            item["app"] = "GitHub CLI (gh)"
            item["host"] = m.group(1) if m else svce
            item["account"] = acct

        elif category == "cursor_token":
            item["app"] = "Cursor"
            item["token_type"] = svce
            item["account"] = acct

        else:
            item["service"] = svce if svce else None
            item["account"] = acct if acct else None

        results.append(item)

    # Sort by category for readability
    order = [
        "google_oauth_native", "github_cli", "cursor_token",
        "electron_safe_storage", "app_token", "api_key_or_secret", "other"
    ]
    results.sort(key=lambda x: (order.index(x["category"]) if x["category"] in order else 99))

    return results


def cmd_get_token(service: str, account: str, **kwargs) -> dict:
    """
    Extract a token value from the Keychain.
    Returns the raw string value (or hex for binary plist entries).
    """
    value = _security(
        "find-generic-password",
        "-s", service,
        "-a", account,
        "-w"
    )

    if not value:
        return {"error": f"No Keychain entry found for service='{service}' account='{account}'"}

    # Detect if it's hex-encoded binary plist (starts with common bplist magic in hex)
    is_hex_plist = bool(re.match(r'^[0-9a-f]{8,}$', value, re.IGNORECASE))

    return {
        "service": service,
        "account": account,
        "value": value,
        "format": "hex_bplist" if is_hex_plist else "string",
        "note": (
            "Binary plist (NSKeyedArchiver). Decode with: "
            "xxd -r -p <<< \"$VALUE\" | plutil -convert json - -o -"
        ) if is_hex_plist else "Plain string token",
    }


def cmd_scan_google_oauth(**kwargs) -> list[dict]:
    """
    Scan /Applications for apps with Google OAuth client IDs.
    Reads Info.plist URL schemes — apps register the reversed client ID
    as a URL scheme so Google can redirect back after login.
    """
    results = []
    apps_dir = Path("/Applications")

    for app_path in sorted(apps_dir.glob("*.app")):
        plist_path = app_path / "Contents" / "Info.plist"
        if not plist_path.exists():
            continue

        try:
            proc = subprocess.run(
                ["plutil", "-convert", "json", str(plist_path), "-o", "-"],
                capture_output=True, text=True, timeout=5
            )
            if proc.returncode != 0:
                continue

            plist = json.loads(proc.stdout)
        except Exception:
            continue

        # Check URL schemes for reversed Google client IDs
        url_types = plist.get("CFBundleURLTypes", [])
        for url_type in url_types:
            for scheme in url_type.get("CFBundleURLSchemes", []):
                if "googleusercontent.apps" in scheme:
                    # Reverse to get the client ID
                    # e.g. com.googleusercontent.apps.1064022179695-abc -> 1064022179695-abc.apps.googleusercontent.com
                    parts = scheme.split(".")
                    # Remove 'com', 'googleusercontent', 'apps' prefix, keep the ID part
                    client_id_part = ".".join(parts[3:]) if len(parts) > 3 else scheme
                    client_id = f"{client_id_part}.apps.googleusercontent.com"

                    results.append({
                        "app": app_path.stem,
                        "bundle_id": plist.get("CFBundleIdentifier"),
                        "version": plist.get("CFBundleShortVersionString"),
                        "client_id": client_id,
                        "url_scheme": scheme,
                        "note": (
                            "Public client ID embedded in app bundle. "
                            "Use with PKCE for token exchange. No secret needed for desktop apps."
                        ),
                    })

    return results
