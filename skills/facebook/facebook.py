"""Facebook skill — public group metadata via HTTP scraping."""

import re
import shutil

from agentos import http, shell


def get_community(
    *,
    group: str = None,
    url: str = None,
    include_members: bool = True,
    **params,
) -> dict:
    """Get metadata for a public Facebook group."""
    # Resolve group name from URL or param
    if url and "facebook.com/groups/" in url:
        m = re.search(r"facebook\.com/groups/([^/]+)", url)
        group_name = m.group(1) if m else (group or "")
    else:
        group_name = group or ""

    group_url = f"https://www.facebook.com/groups/{group_name}/"

    # Fetch the page
    resp = http.get(group_url, timeout=30.0)

    html = resp["body"]
    if not html:
        return {"error": "Failed to fetch group page. Group may be private or not found."}

    # Extract metadata from meta tags
    group_id = ""
    m = re.search(r"fb://group/(\d+)", html)
    if m:
        group_id = m.group(1)

    title = ""
    m = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"', html)
    if m:
        title = re.sub(r"\s*\|\s*Facebook$", "", m.group(1))

    description = ""
    m = re.search(r'<meta[^>]*property="og:description"[^>]*content="([^"]+)"', html)
    if m:
        description = m.group(1)

    og_image = ""
    m = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html)
    if m:
        og_image = m.group(1)

    # Member count via headless Chromium (optional, slower)
    member_count_raw = ""
    member_count_numeric = None

    if include_members:
        chromium = _find_chromium()
        if chromium:
            try:
                result = shell.run(chromium, ["--headless", "--dump-dom", group_url], timeout=20)
                dom = result["stdout"]
                if dom:
                    mc = re.search(r"([\d,.]+K?)\s*members?", dom)
                    if mc:
                        member_count_raw = mc.group(1)
                        member_count_numeric = _parse_member_count(member_count_raw)
            except Exception:
                pass

    return {
        "id": group_id,
        "name": title,
        "description": description,
        "url": group_url,
        "icon": og_image,
        "member_count_raw": member_count_raw,
        "member_count_numeric": member_count_numeric,
        "privacy": "OPEN",
    }


def _find_chromium() -> str | None:
    """Find a Chromium binary on the system."""
    if shutil.which("chromium"):
        return "chromium"
    mac_path = "/Applications/Chromium.app/Contents/MacOS/Chromium"
    import os
    if os.path.isfile(mac_path):
        return mac_path
    if shutil.which("chromium-browser"):
        return "chromium-browser"
    return None


def _parse_member_count(raw: str) -> int | None:
    """Parse '12,345' or '1.2K' or '3.5M' into an integer."""
    cleaned = raw.replace(",", "")
    if cleaned.endswith("K"):
        try:
            return int(float(cleaned[:-1]) * 1000)
        except ValueError:
            return None
    if cleaned.endswith("M"):
        try:
            return int(float(cleaned[:-1]) * 1_000_000)
        except ValueError:
            return None
    try:
        return int(cleaned)
    except ValueError:
        return None
