"""
macOS Security skill — Keychain audit, token extraction, OAuth app scanning.

All operations run locally against the macOS Keychain and /Applications.
No network calls. Requires macOS.
"""

import json
import os
import re
from pathlib import Path

from agentos import shell, sql


# ── App discovery ──────────────────────────────────────────────────────────────

_APP_DIRS = [
    Path("/Applications"),
    Path("/Applications/Setapp"),
    Path.home() / "Applications",
    Path("/System/Applications"),
]

def _find_all_apps() -> list[Path]:
    """Find .app bundles across all common install locations."""
    seen: set[Path] = set()
    apps: list[Path] = []
    for base in _APP_DIRS:
        if not base.exists():
            continue
        for app_path in sorted(base.glob("*.app")):
            if app_path not in seen:
                seen.add(app_path)
                apps.append(app_path)
    return apps


def _read_plist_json(plist_path: Path) -> dict | None:
    """Parse an Info.plist file to a dict via plutil."""
    try:
        result = shell.run("plutil", ["-convert", "json", str(plist_path), "-o", "-"], timeout=5)
        if result["exit_code"] != 0:
            return None
        return json.loads(result["stdout"])
    except Exception:
        return None


# ── Keychain helpers ───────────────────────────────────────────────────────────

def _security(*args) -> str:
    """Run a `security` CLI command, return stdout."""
    result = shell.run("security", list(args))
    return result["stdout"].strip()


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
        if line.startswith("keychain:"):
            if current:
                entries.append(current)
            current = {}
            continue

        m = re.search(r'"(\w+)"<\w+>="([^"]*)"', line)
        if m:
            current[m.group(1)] = m.group(2)
            continue

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


# Match "AppName: email@domain" — native OAuth pattern used by Mimestream, BusyContacts, etc.
_NATIVE_OAUTH = re.compile(r"^(.+): (.+@.+)$")
_SAFE_STORAGE = re.compile(r"^(.+) Safe Storage$")
_GH_CLI       = re.compile(r"^gh:(.+)$")
_CURSOR_TOK   = re.compile(r"^cursor-(access|refresh)-token$")
# Spark uses its own account auth service names
_SPARK        = re.compile(r"^(SparkDesktop|com\.readdle\.spark\..+)$")

def _categorize(entry: dict) -> str | None:
    svce = entry.get("svce") or ""
    acct = entry.get("acct") or ""

    if _SAFE_STORAGE.match(svce):
        return "electron_safe_storage"
    if _NATIVE_OAUTH.match(svce) and acct == "OAuth":
        return "google_oauth_native"
    if _SPARK.match(svce):
        return "spark_auth"
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

        if category == "electronSafeStorage":
            m = _SAFE_STORAGE.match(svce)
            item["app"] = m.group(1) if m else svce
            item["note"] = "Master encryption key for all locally stored credentials"
            app_support = Path.home() / "Library" / "Application Support" / item["app"]
            if app_support.exists():
                item["data_path"] = str(app_support)

        elif category == "googleOauthNative":
            m = _NATIVE_OAUTH.match(svce)
            item["app"] = m.group(1) if m else svce
            item["account"] = m.group(2) if m else acct
            item["service_name"] = svce
            item["account_name"] = acct
            item["note"] = "Native Google OAuth tokens stored by app in Keychain"

        elif category == "sparkAuth":
            item["app"] = "Spark"
            item["service"] = svce
            item["account"] = acct
            item["note"] = "Spark account auth key (Secure Enclave or RSA)"

        elif category == "githubCli":
            m = _GH_CLI.match(svce)
            item["app"] = "GitHub CLI (gh)"
            item["host"] = m.group(1) if m else svce
            item["account"] = acct

        elif category == "cursorToken":
            item["app"] = "Cursor"
            item["token_type"] = svce
            item["account"] = acct

        else:
            item["service"] = svce if svce else None
            item["account"] = acct if acct else None

        results.append(item)

    order = [
        "google_oauth_native", "spark_auth", "github_cli", "cursor_token",
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
    Scan all installed apps for Google OAuth client IDs.
    Searches /Applications, /Applications/Setapp, ~/Applications, /System/Applications.
    Reads Info.plist URL schemes — apps register the reversed client ID
    as a URL scheme so Google can redirect back after login.
    """
    results = []

    for app_path in _find_all_apps():
        plist_path = app_path / "Contents" / "Info.plist"
        if not plist_path.exists():
            continue

        plist = _read_plist_json(plist_path)
        if plist is None:
            continue

        url_types = plist.get("CFBundleURLTypes", [])
        for url_type in url_types:
            for scheme in url_type.get("CFBundleURLSchemes", []):
                if "googleusercontent.apps" in scheme:
                    parts = scheme.split(".")
                    client_id_part = ".".join(parts[3:]) if len(parts) > 3 else scheme
                    client_id = f"{client_id_part}.apps.googleusercontent.com"

                    results.append({
                        "app": app_path.stem,
                        "installPath": str(app_path),
                        "bundleId": plist.get("CFBundleIdentifier"),
                        "version": plist.get("CFBundleShortVersionString"),
                        "clientId": client_id,
                        "urlScheme": scheme,
                        "note": (
                            "Public client ID embedded in app bundle. "
                            "Use with PKCE for token exchange. No secret needed for desktop apps."
                        ),
                    })

    return results


def cmd_scan_macos_accounts(**kwargs) -> list[dict]:
    """
    Scan macOS Internet Accounts (Account.framework).
    These are OS-level OAuth connections added via System Settings → Internet Accounts.
    The 'macOS' entry in Google's authorized apps list comes from here.
    Requires Full Disk Access — returns a permission error if denied.
    """
    accounts_dir = Path.home() / "Library" / "Accounts"

    # macOS uses Accounts3, 4, or 5 depending on version
    accounts_db = None
    for name in ("Accounts5.sqlite", "Accounts4.sqlite", "Accounts3.sqlite"):
        candidate = accounts_dir / name
        if candidate.exists():
            accounts_db = candidate
            break

    if accounts_db is None:
        return [{"error": "No Accounts DB found in ~/Library/Accounts/", "note": "Grant Full Disk Access to enable"}]

    results = []
    db = str(accounts_db)

    try:
        # Check schema
        tables_rows = sql.query("SELECT name FROM sqlite_master WHERE type='table'", db=db)
        tables = {r["name"] for r in tables_rows}

        if "ZACCOUNT" not in tables:
            return [{"error": "Unexpected DB schema — ZACCOUNT table not found"}]

        has_type_table = "ZACCOUNTTYPE" in tables

        if has_type_table:
            rows = sql.query("""
                SELECT
                    a.ZUSERNAME   AS username,
                    a.ZIDENTIFIER AS identifier,
                    t.ZIDENTIFIER AS account_type
                FROM ZACCOUNT a
                LEFT JOIN ZACCOUNTTYPE t ON a.ZACCOUNTTYPE = t.Z_PK
                ORDER BY t.ZIDENTIFIER, a.ZUSERNAME
            """, db=db)
        else:
            rows = sql.query("""
                SELECT ZUSERNAME AS username, ZIDENTIFIER AS identifier, NULL AS account_type
                FROM ZACCOUNT
                ORDER BY ZUSERNAME
            """, db=db)

        # Only show top-level provider accounts (Google, Exchange, etc.)
        _SHOW_TYPES = {
            "com.apple.account.Google",
            "com.apple.account.Exchange",
            "com.apple.account.Facebook",
            "com.apple.account.Twitter",
            "com.apple.account.LinkedIn",
        }

        for row in rows:
            account_type = row.get("account_type") or ""
            if account_type not in _SHOW_TYPES:
                continue
            username = row.get("username") or row.get("identifier") or ""
            if re.match(r'^[0-9A-F]{8}-', username):
                continue
            results.append({
                "username": username,
                "accountType": account_type or "unknown",
                "identifier": row.get("identifier"),
                "note": _account_type_note(account_type),
            })

    except Exception as e:
        err_msg = str(e)
        if "unable to open" in err_msg or "permission" in err_msg.lower():
            return [{
                "error": "Permission denied reading Accounts5.sqlite",
                "note": "Grant Full Disk Access to Terminal or Claude in System Settings → Privacy",
            }]
        return [{"error": err_msg}]

    return results


def _account_type_note(account_type: str) -> str:
    notes = {
        "com.apple.account.Google": "Google account — Calendar, Contacts, Mail via macOS",
        "com.apple.account.Exchange": "Microsoft Exchange account",
        "com.apple.account.Facebook": "Facebook account (deprecated in newer macOS)",
        "com.apple.account.Twitter": "Twitter/X account (deprecated in newer macOS)",
        "com.apple.account.LinkedIn": "LinkedIn account (deprecated in newer macOS)",
        "com.apple.account.CardDAV": "CardDAV contacts account",
        "com.apple.account.CalDAV": "CalDAV calendar account",
        "com.apple.account.IMAP": "IMAP email account",
    }
    for key, note in notes.items():
        if account_type.startswith(key):
            return note
    return "macOS Internet Account"


def cmd_list_electron_apps(**kwargs) -> list[dict]:
    """
    List all apps using the Electron Safe Storage pattern.
    Each stores a master encryption key in the Keychain that encrypts all
    locally stored credentials, cookies, and session data.
    """
    dump = _dump_keychain()
    names: set[str] = set()
    for line in dump.splitlines():
        if "Safe Storage" not in line:
            continue
        m = re.search(r'"([^"]*) Safe Storage"', line)
        if m:
            names.add(m.group(1))
    return [{"name": name} for name in sorted(names)]
