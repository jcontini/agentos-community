#!/usr/bin/env python3
"""Verify that api and cache sources work independently.

Proves:
  1. Cache works without network (mocks urllib to block all HTTP)
  2. API works and returns data from network (not cache)
  3. source param actually routes to different code paths

Run: python3 test-sources.py
"""

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import granola

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"  ✓ {msg}")

def fail(msg):
    global FAIL
    FAIL += 1
    print(f"  ✗ {msg}")

def check(condition, msg):
    if condition:
        ok(msg)
    else:
        fail(msg)


# ── Test 1: Cache works with network completely blocked ───────────────────────

print("\n── Test 1: cache works without network")

def blocked_urlopen(*args, **kwargs):
    raise ConnectionError("Network blocked by test harness")

with patch("granola.urlopen", side_effect=blocked_urlopen):
    try:
        cache_meetings = granola.op_list_meetings(limit=5, page=0, source="cache")
        check(isinstance(cache_meetings, list), f"cache returns list ({len(cache_meetings)} meetings)")
        check(len(cache_meetings) > 0, "cache has meetings")
        if cache_meetings:
            check("title" in cache_meetings[0], "cache meetings have title field")
            check("id" in cache_meetings[0], "cache meetings have id field")
    except SystemExit:
        fail("cache source hit SystemExit (probably tried network)")
    except Exception as e:
        fail(f"cache source raised: {e}")


# ── Test 2: API returns data from network ─────────────────────────────────────

print("\n── Test 2: api returns data from network")

try:
    api_meetings = granola.op_list_meetings(limit=5, page=0, source="api")
    check(isinstance(api_meetings, list), f"api returns list ({len(api_meetings)} meetings)")
    check(len(api_meetings) > 0, "api has meetings")
except SystemExit as e:
    fail(f"api source hit SystemExit: {e}")
except Exception as e:
    fail(f"api source raised: {e}")


# ── Test 3: API and cache are actually different code paths ───────────────────

print("\n── Test 3: api actually hits network (not cache)")

call_log = []
original_urlopen = granola.urlopen

def tracking_urlopen(req, *args, **kwargs):
    url = req.full_url if hasattr(req, 'full_url') else str(req)
    call_log.append(url)
    return original_urlopen(req, *args, **kwargs)

with patch("granola.urlopen", side_effect=tracking_urlopen):
    call_log.clear()
    granola.op_list_meetings(limit=2, page=0, source="api")
    check(len(call_log) > 0, f"api made {len(call_log)} HTTP call(s): {call_log}")

    call_log.clear()
    granola.op_list_meetings(limit=2, page=0, source="cache")
    check(len(call_log) == 0, f"cache made {len(call_log)} HTTP calls (should be 0)")


# ── Test 4: conversations also respect source ─────────────────────────────────

print("\n── Test 4: list_conversations respects source param")

if api_meetings:
    doc_id = api_meetings[0]["id"]

    with patch("granola.urlopen", side_effect=blocked_urlopen):
        try:
            cache_convos = granola.op_list_conversations(document_id=doc_id, source="cache")
            check(isinstance(cache_convos, list), f"cache conversations returns list ({len(cache_convos)})")
        except SystemExit:
            fail("cache conversations tried to hit network")
        except Exception as e:
            fail(f"cache conversations raised: {e}")
else:
    print("  (skipped — no meetings found)")


# ── Test 5: auto falls back from api to cache ────────────────────────────────

print("\n── Test 5: auto source falls back to cache when network fails")

with patch("granola.urlopen", side_effect=blocked_urlopen):
    with patch("granola.get_token", side_effect=SystemExit("token fail")):
        try:
            auto_meetings = granola.op_list_meetings(limit=3, page=0, source="auto")
            check(isinstance(auto_meetings, list), f"auto fallback returns list ({len(auto_meetings)} meetings)")
            check(len(auto_meetings) > 0, "auto fallback has meetings from cache")
        except SystemExit:
            fail("auto source did not fall back to cache")
        except Exception as e:
            fail(f"auto source raised: {e}")


# ── Summary ──────────────────────────────────────────────────────────────────

print(f"\n{'='*50}")
print(f"  {PASS} passed, {FAIL} failed")
print(f"{'='*50}")
sys.exit(1 if FAIL > 0 else 0)
