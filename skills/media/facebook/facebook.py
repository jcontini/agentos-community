"""Facebook skill — public group metadata via HTTP scraping."""

import re
import shutil

from lxml import html as lhtml
from agentos import http, shell, provides, returns, timeout, web_read


@returns("community")
@provides(web_read, urls=["facebook.com/groups/*", "www.facebook.com/groups/*"])
@timeout(35)
async def get_community(
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
    resp = await http.get(group_url, timeout=30.0)

    html = resp["body"]
    if not html:
        raise ValueError("Failed to fetch group page. Group may be private or not found.")

    # Extract metadata from meta tags via CSS selectors
    doc = lhtml.fromstring(html)

    group_id = ""
    m = re.search(r"fb://group/(\d+)", html)
    if m:
        group_id = m.group(1)

    og_title = doc.cssselect('meta[property="og:title"]')
    title = re.sub(r"\s*\|\s*Facebook$", "", og_title[0].get("content", "")) if og_title else ""

    og_desc = doc.cssselect('meta[property="og:description"]')
    description = og_desc[0].get("content", "") if og_desc else ""

    og_img = doc.cssselect('meta[property="og:image"]')
    og_image = og_img[0].get("content", "") if og_img else ""

    # Member count via headless Chromium (optional, slower)
    member_count_raw = ""
    member_count_numeric = None

    if include_members:
        chromium = _find_chromium()
        if chromium:
            try:
                result = await shell.run(chromium, ["--headless", "--dump-dom", group_url], timeout=20)
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
        "content": description,
        "url": group_url,
        "image": og_image,
        "memberCount": member_count_numeric,
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
