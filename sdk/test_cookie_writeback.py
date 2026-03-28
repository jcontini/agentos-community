#!/usr/bin/env python3
"""Verify cookie writeback tracking in surf().

Gate test for cookie-jar spec Step 1: SDK writeback collection.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agentos.http import (
    surf,
    _tracked_clients,
    _snapshot_jar,
    _collect_cookie_writeback,
)


def test_unchanged_cookies_produce_no_writeback():
    """If no cookies changed, writeback returns None."""
    _tracked_clients.clear()
    client = surf(http2=False, cookies="sid=abc; lang=en")
    # Don't touch any cookies
    wb = _collect_cookie_writeback()
    assert wb is None, f"Expected None, got {wb}"
    assert len(_tracked_clients) == 0, "Registry should be cleared"


def test_changed_cookie_detected():
    """A rotated cookie appears in writeback."""
    _tracked_clients.clear()
    client = surf(http2=False, cookies="token=old; sid=abc")
    # Simulate server rotating the token via Set-Cookie
    client.cookies.set("token", "new", domain="")
    wb = _collect_cookie_writeback()
    assert wb is not None, "Expected writeback for changed cookie"
    names = {c["name"] for c in wb}
    assert "token" in names, f"Expected 'token' in writeback, got {names}"
    assert "sid" not in names, "Unchanged 'sid' should not be in writeback"
    token_entry = next(c for c in wb if c["name"] == "token")
    assert token_entry["value"] == "new"


def test_new_cookie_detected():
    """A cookie added by Set-Cookie (not in initial) appears in writeback."""
    _tracked_clients.clear()
    client = surf(http2=False, cookies="sid=abc")
    client.cookies.set("newcookie", "val", domain="")
    wb = _collect_cookie_writeback()
    assert wb is not None
    names = {c["name"] for c in wb}
    assert "newcookie" in names
    assert "sid" not in names


def test_multiple_surf_calls_tracked():
    """Multiple surf() calls in one skill all contribute to writeback."""
    _tracked_clients.clear()
    client1 = surf(http2=False, cookies="a=1")
    client2 = surf(http2=False, cookies="b=2")
    client1.cookies.set("a", "changed", domain="")
    client2.cookies.set("b", "changed", domain="")
    wb = _collect_cookie_writeback()
    assert wb is not None
    names = {c["name"] for c in wb}
    assert names == {"a", "b"}


def test_no_cookies_no_tracking():
    """surf() without cookies doesn't register for tracking."""
    _tracked_clients.clear()
    client = surf(http2=False)  # No cookies
    assert len(_tracked_clients) == 0
    wb = _collect_cookie_writeback()
    assert wb is None


def test_registry_cleared_after_collection():
    """_collect_cookie_writeback() clears the registry."""
    _tracked_clients.clear()
    client = surf(http2=False, cookies="x=1")
    client.cookies.set("x", "2", domain="")
    wb1 = _collect_cookie_writeback()
    assert wb1 is not None
    # Second collection should return None (registry cleared)
    wb2 = _collect_cookie_writeback()
    assert wb2 is None


def test_domain_dot_normalization():
    """Leading dots on domains are stripped for consistent diffing."""
    _tracked_clients.clear()
    client = surf(http2=False, cookies="sid=abc")
    # Simulate a Set-Cookie with dotted domain (as httpx does from real responses)
    client.cookies.jar.set_cookie(
        _make_cookie("sid", "new", ".example.com")
    )
    wb = _collect_cookie_writeback()
    assert wb is not None
    entry = wb[0]
    assert entry["domain"] == "example.com", f"Expected dotless domain, got {entry['domain']}"


def _make_cookie(name, value, domain):
    """Create an http.cookiejar.Cookie for testing."""
    import http.cookiejar
    import time

    return http.cookiejar.Cookie(
        version=0,
        name=name,
        value=value,
        port=None,
        port_specified=False,
        domain=domain,
        domain_specified=bool(domain),
        domain_initial_dot=domain.startswith("."),
        path="/",
        path_specified=True,
        secure=False,
        expires=int(time.time()) + 3600,
        discard=False,
        comment=None,
        comment_url=None,
        rest={},
    )


if __name__ == "__main__":
    tests = [
        test_unchanged_cookies_produce_no_writeback,
        test_changed_cookie_detected,
        test_new_cookie_detected,
        test_multiple_surf_calls_tracked,
        test_no_cookies_no_tracking,
        test_registry_cleared_after_collection,
        test_domain_dot_normalization,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  ✓ {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {test.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
