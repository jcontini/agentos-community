# Apple Biome — Skill for AI Agents

How to extract app usage, media playback, web browsing, device connectivity, location, and other behavioral data from macOS. Covers both local Mac data and cross-device iPhone/iPad data synced via iCloud through Apple's Biome framework.

Use when the user asks about app usage, screen time, what they've been listening to, browsing history, location, device activity, or wants behavioral data for charts/analysis.

---

## Quick Reference

| Data | Source | Path |
|------|--------|------|
| macOS app usage | Knowledge DB (SQLite) | `~/Library/Application Support/Knowledge/knowledgeC.db` |
| Cross-device app usage | Biome `App.InFocus` | `~/Library/Biome/streams/restricted/App.InFocus/` |
| Now playing media | Biome `Media.NowPlaying` | `~/Library/Biome/streams/restricted/Media.NowPlaying/` |
| Website visits | Biome `App.WebUsage` | `~/Library/Biome/streams/restricted/App.WebUsage/` |
| WiFi connections | Biome `Device.Wireless.WiFi` | `~/Library/Biome/streams/restricted/Device.Wireless.WiFi/` |
| Bluetooth devices | Biome `Device.Wireless.Bluetooth` | `~/Library/Biome/streams/restricted/Device.Wireless.Bluetooth/` |
| Notifications | Biome `Notification.Usage` | `~/Library/Biome/streams/restricted/Notification.Usage/` |
| Documents opened | Biome `App.DocumentInteraction` | `~/Library/Biome/streams/restricted/App.DocumentInteraction/` |
| Focus modes | Biome `UserFocus.ComputedMode` | `~/Library/Biome/streams/restricted/UserFocus.ComputedMode/` |
| Safari browsing | Biome `ProactiveHarvesting.Safari.PageView` | `~/Library/Biome/streams/restricted/ProactiveHarvesting.Safari.PageView/` |
| Current location | Weather DB (SQLite) | `~/Library/Weather/current-location.db` |

**Requirements:** Screen Time must be enabled. Cross-device data requires "Share across devices" in Screen Time settings.

---

## Bundle ID Resolution

Apps are identified by bundle IDs (e.g. `com.spotify.client`). Resolve them to human-readable names programmatically — never hardcode a mapping table.

### Resolution chain

1. **mdfind + Info.plist** — for macOS-installed apps (instant, local)
2. **iTunes Search API** — for iOS/iPadOS apps (network call, covers everything in the App Store)
3. **Heuristic fallback** — derive from the bundle ID itself

```python
import subprocess
import plistlib
import os
import json
import urllib.request

def resolve_bundle_id(bundle_id):
    """
    Resolve an Apple bundle ID to a human-readable app name.
    Tries local macOS lookup first, then iTunes API, then heuristic.
    """
    # Method 1: mdfind (local macOS apps — instant)
    try:
        result = subprocess.run(
            ['mdfind', f'kMDItemCFBundleIdentifier == "{bundle_id}"'],
            capture_output=True, text=True, timeout=5
        )
        app_path = result.stdout.strip().split('\n')[0]
        if app_path and app_path.endswith('.app'):
            plist_path = os.path.join(app_path, 'Contents', 'Info.plist')
            if os.path.exists(plist_path):
                with open(plist_path, 'rb') as f:
                    info = plistlib.load(f)
                name = info.get('CFBundleDisplayName') or info.get('CFBundleName')
                if name:
                    return name
            return os.path.basename(app_path).replace('.app', '')
    except Exception:
        pass

    # Method 2: iTunes Search API (iOS/iPadOS apps)
    try:
        url = f"https://itunes.apple.com/lookup?bundleId={bundle_id}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
        if data.get('resultCount', 0) > 0:
            name = data['results'][0]['trackName']
            # Strip common suffixes like "- Request a ride"
            if ':' in name:
                name = name.split(':')[0].strip()
            elif ' - ' in name:
                name = name.split(' - ')[0].strip()
            return name
    except Exception:
        pass

    # Method 3: Heuristic from bundle ID
    parts = bundle_id.split('.')
    if len(parts) >= 2:
        candidate = parts[-1]
        if candidate.lower() in ('ios', 'app', 'mobile', 'client', 'iphone', 'macos'):
            candidate = parts[-2] if len(parts) >= 3 else candidate
        return candidate.replace('-', ' ').replace('_', ' ').title()

    return bundle_id


def resolve_bundle_ids(bundle_ids):
    """
    Batch-resolve a list of bundle IDs. Returns dict of {bundle_id: app_name}.
    Uses a cache to avoid redundant lookups.
    """
    cache = {}
    for bid in bundle_ids:
        if bid not in cache:
            cache[bid] = resolve_bundle_id(bid)
    return cache
```

**Performance note:** `mdfind` is instant for macOS apps. The iTunes API adds ~100ms per lookup but is only called for iOS-only apps. For batch resolution, the cache prevents duplicate lookups. For performance-sensitive code, resolve after aggregation (resolve the top 20 apps, not every event).

---

## Method 1: macOS Screen Time (Simple)

Query the Knowledge DB directly with SQLite. This only returns macOS app usage.

### Top apps by hours (last N days)

```python
import sqlite3
import os

db_path = os.path.expanduser("~/Library/Application Support/Knowledge/knowledgeC.db")
conn = sqlite3.connect(db_path)

days = 90  # adjust as needed
cursor = conn.execute("""
    SELECT
        ZOBJECT.ZVALUESTRING as app_id,
        ROUND(SUM(ZOBJECT.ZENDDATE - ZOBJECT.ZSTARTDATE) / 3600.0, 2) as hours
    FROM ZOBJECT
    WHERE ZSTREAMNAME = '/app/usage'
        AND ZSTARTDATE > (strftime('%s', 'now') - 978307200 - ?*86400)
    GROUP BY ZOBJECT.ZVALUESTRING
    ORDER BY hours DESC
    LIMIT 20
""", (days,))

names = resolve_bundle_ids([row[0] for row in cursor.fetchall()])
cursor = conn.execute("""...""", (days,))  # re-execute after consuming

for app_id, hours in cursor:
    print(f"{names.get(app_id, app_id)}: {hours}h")

conn.close()
```

### Timestamps

Knowledge DB uses **Core Data timestamps** — seconds since 2001-01-01 00:00:00 UTC.

```python
import datetime

def core_data_to_datetime(ts):
    """Convert Core Data timestamp to Python datetime."""
    return datetime.datetime(2001, 1, 1) + datetime.timedelta(seconds=ts)

def datetime_to_core_data(dt):
    """Convert Python datetime to Core Data timestamp."""
    return (dt - datetime.datetime(2001, 1, 1)).total_seconds()
```

To compare with Unix time: `unix_timestamp = core_data_timestamp + 978307200`.

---

## Method 2: Apple Biome (Cross-Device, Advanced)

### What is Biome?

Apple Biome is a distributed event store built into macOS, iOS, and iPadOS. It records timestamped behavioral events — app switches, media playback, WiFi connections, focus modes, notifications, and more — and syncs them across devices via iCloud using CRDTs for conflict resolution.

### Directory Structure

```
~/Library/Biome/
├── streams/
│   ├── restricted/              # Most streams live here
│   │   ├── App.InFocus/
│   │   │   ├── local/           # Events from this Mac
│   │   │   │   └── 0            # SEGB binary files (numbered)
│   │   │   │   └── 1
│   │   │   └── remote/          # Events synced from other devices
│   │   │       ├── {uuid-1}/    # iPhone
│   │   │       └── {uuid-2}/    # iPad
│   │   ├── Media.NowPlaying/
│   │   │   ├── local/
│   │   │   └── remote/
│   │   └── ...
│   └── public/                  # Rarely used
└── sync/
    └── sync.db                  # CloudKit sync metadata
```

Each stream has `local/` data (this device) and optionally `remote/{device-uuid}/` data (other iCloud-connected devices). Data files are numbered SEGB (Segment Binary) files.

### Device Discovery

```bash
# List all remote devices that have synced data
ls ~/Library/Biome/streams/restricted/App.InFocus/remote/

# Get this Mac's hardware UUID (to exclude it from remote list)
system_profiler SPHardwareDataType | grep "Hardware UUID"
```

To identify which device is which, check what apps it runs:

```bash
# iOS devices will have mobile-specific bundle IDs
strings ~/Library/Biome/streams/restricted/App.InFocus/remote/{device-id}/* | \
  grep -oE "(com|co|net)\.[a-zA-Z0-9_.]+" | sort -u | head -20
```

**iOS indicators:** `com.apple.MobileSMS`, `com.apple.camera`, `com.apple.springboard`, bundle IDs ending in `.ios` or `.iphone`.

---

### SEGB File Format

All Biome data is stored in SEGB (Segment Binary) files. The base parser:

```python
import struct
import datetime
import re

def parse_segb_strings(filepath):
    """
    Parse a Biome SEGB file and extract timestamped events with string data.
    Returns list of (datetime, [strings]) tuples.

    This is a general-purpose parser. Each stream embeds different data,
    but they all share the SEGB container format with Core Data timestamps
    and protobuf-encoded entries containing readable strings.
    """
    with open(filepath, 'rb') as f:
        data = f.read()

    if data[:4] != b'SEGB':
        return []

    events = []
    i = 32  # skip header

    while i < len(data) - 8:
        try:
            ts = struct.unpack_from('<d', data, i)[0]
            # Valid Core Data timestamp range (~2023-2028)
            if 700000000 < ts < 900000000:
                dt = core_data_to_datetime(ts)
                # Extract readable strings from nearby bytes
                search_area = data[i:i+512]
                strings = re.findall(rb'[\x20-\x7e]{4,}', search_area)
                decoded = [s.decode('ascii', errors='ignore') for s in strings]
                if decoded:
                    events.append((dt, decoded))
                    i += 8
                    continue
        except struct.error:
            pass
        i += 1

    return events
```

---

### Stream: App.InFocus (Screen Time)

Records every foreground app transition. The primary stream for screen time data.

**Data:** timestamp + bundle ID (which app came to foreground)

```python
def parse_app_infocus(filepath):
    """Parse App.InFocus SEGB file. Returns [(datetime, bundle_id), ...]."""
    with open(filepath, 'rb') as f:
        data = f.read()

    if data[:4] != b'SEGB':
        return []

    events = []
    i = 32

    while i < len(data) - 8:
        try:
            ts = struct.unpack_from('<d', data, i)[0]
            if 700000000 < ts < 900000000:
                search_area = data[i:i+200]
                bid_match = re.search(
                    rb'(com\.[a-zA-Z0-9_.]+|co\.[a-zA-Z0-9_.]+|net\.[a-zA-Z0-9_.]+|org\.[a-zA-Z0-9_.]+)',
                    search_area
                )
                if bid_match:
                    bid = bid_match.group(0).decode('ascii')
                    bid = re.sub(r'[JhR]$', '', bid)  # clean trailing protobuf markers
                    dt = core_data_to_datetime(ts)
                    events.append((dt, bid))
                    i += 8
                    continue
        except (struct.error, UnicodeDecodeError):
            pass
        i += 1

    return events
```

#### Calculate usage duration

Each event means "this app came to the foreground." Duration = time until the next event.

```python
import os
import glob

def get_device_usage(device_path, days=7):
    """
    Calculate app usage for a device. Pass the full path to the device directory:
      - local:  ~/Library/Biome/streams/restricted/App.InFocus/local
      - remote: ~/Library/Biome/streams/restricted/App.InFocus/remote/{device-id}

    Returns dict of {bundle_id: total_seconds}.
    """
    all_events = []
    for filepath in glob.glob(os.path.join(device_path, "[0-9]*")):
        all_events.extend(parse_app_infocus(filepath))

    all_events.sort(key=lambda x: x[0])

    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    events = [(dt, bid) for dt, bid in all_events if dt >= cutoff]

    # System/UI apps to exclude
    system_prefixes = [
        'com.apple.SpringBoard', 'com.apple.SleepLockScreen',
        'com.apple.control', 'com.apple.springboard',
        'com.apple.InCallService', 'com.apple.PassbookUIService',
    ]

    def is_user_app(bid):
        return not any(bid.startswith(p) for p in system_prefixes)

    usage = {}
    for j in range(len(events) - 1):
        app = events[j][1]
        if not is_user_app(app):
            continue
        duration = (events[j+1][0] - events[j][0]).total_seconds()
        # Cap sessions at 1 hour (filters sleep/overnight gaps)
        if 0 < duration < 3600:
            usage[app] = usage.get(app, 0) + duration

    return usage


def fmt_time(secs):
    """Format seconds as human-readable time."""
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    return f"{h}h {m:02d}m" if h > 0 else f"{m}m"
```

#### Full example: all devices

```python
import os

base = os.path.expanduser("~/Library/Biome/streams/restricted/App.InFocus")

# Local Mac usage
print("=== This Mac ===")
usage = get_device_usage(os.path.join(base, "local"), days=7)
names = resolve_bundle_ids(list(usage.keys()))
for bid, secs in sorted(usage.items(), key=lambda x: -x[1])[:15]:
    print(f"  {names[bid]:<30} {fmt_time(secs):>10}")

# Remote devices
remote_dir = os.path.join(base, "remote")
if os.path.exists(remote_dir):
    for device_id in os.listdir(remote_dir):
        device_path = os.path.join(remote_dir, device_id)
        if not os.path.isdir(device_path):
            continue
        usage = get_device_usage(device_path, days=7)
        if not usage:
            continue
        names = resolve_bundle_ids(list(usage.keys()))
        # Detect device type from bundle IDs
        ios_signals = sum(1 for b in usage if any(
            x in b for x in ['.ios', '.iphone', 'MobileSMS', '.camera', '.springboard']
        ))
        device_type = "iPhone/iPad" if ios_signals > 0 else "Mac/Other"
        print(f"\n=== {device_type} ({device_id[:8]}...) ===")
        for bid, secs in sorted(usage.items(), key=lambda x: -x[1])[:15]:
            print(f"  {names[bid]:<30} {fmt_time(secs):>10}")
```

---

### Stream: Media.NowPlaying

Records what's currently playing — song name, artist, album, media type, and which app is playing it. Syncs cross-device.

**Data per event:** track name, artist name, album name, media type, source app bundle ID

```python
def parse_media_now_playing(filepath):
    """
    Parse Media.NowPlaying SEGB file.
    Returns [(datetime, {'track': str, 'artist': str, 'album': str, 'app': str}), ...]
    """
    with open(filepath, 'rb') as f:
        data = f.read()

    if data[:4] != b'SEGB':
        return []

    events = []
    i = 32

    while i < len(data) - 8:
        try:
            ts = struct.unpack_from('<d', data, i)[0]
            if 700000000 < ts < 900000000:
                dt = core_data_to_datetime(ts)
                search_area = data[i:i+512]

                # Extract readable strings (track, artist, album are embedded)
                strings_found = re.findall(rb'[\x20-\x7e]{3,}', search_area)
                decoded = [s.decode('ascii', errors='ignore') for s in strings_found]

                # Find bundle ID
                bid_match = re.search(
                    rb'(com\.[a-zA-Z0-9_.]+|co\.[a-zA-Z0-9_.]+|net\.[a-zA-Z0-9_.]+)',
                    search_area
                )
                app = bid_match.group(0).decode('ascii') if bid_match else None

                # The protobuf structure typically has: track, artist, album as
                # the longest non-bundle-ID strings in the record
                text_strings = [s for s in decoded
                                if not s.startswith(('com.', 'co.', 'net.', 'kMR'))
                                and len(s) > 2]

                if text_strings:
                    events.append((dt, {
                        'strings': text_strings,
                        'app': app,
                    }))
                    i += 8
                    continue
        except struct.error:
            pass
        i += 1

    return events
```

**Usage:** Check what someone's been listening to, build listening history, correlate music with activities.

---

### Stream: App.WebUsage

Records website visits within apps — full URLs, domains, and which browser/app.

**Data per event:** full URL, domain, browser bundle ID, tab/window UUID

```python
def parse_web_usage(filepath):
    """
    Parse App.WebUsage SEGB file.
    Returns [(datetime, {'url': str, 'domain': str, 'app': str}), ...]
    """
    with open(filepath, 'rb') as f:
        data = f.read()

    if data[:4] != b'SEGB':
        return []

    events = []
    i = 32

    while i < len(data) - 8:
        try:
            ts = struct.unpack_from('<d', data, i)[0]
            if 700000000 < ts < 900000000:
                dt = core_data_to_datetime(ts)
                search_area = data[i:i+1024]

                url_match = re.search(rb'https?://[^\x00-\x1f]+', search_area)
                bid_match = re.search(
                    rb'(com\.[a-zA-Z0-9_.]+|co\.[a-zA-Z0-9_.]+)',
                    search_area
                )

                if url_match:
                    url = url_match.group(0).decode('ascii', errors='ignore')
                    # Extract domain from nearby strings
                    domain_match = re.search(
                        rb'[a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,}',
                        search_area
                    )
                    events.append((dt, {
                        'url': url,
                        'domain': domain_match.group(0).decode('ascii') if domain_match else None,
                        'app': bid_match.group(0).decode('ascii') if bid_match else None,
                    }))
                    i += 8
                    continue
        except struct.error:
            pass
        i += 1

    return events
```

---

### Stream: Device.Wireless.WiFi

Records WiFi **connection and disconnection** events. Only networks you actually join — not scanned/broadcast networks. Useful for location inference (home vs office vs travel).

**Data per event:** SSID (network name), connected/disconnected state

**Note:** This stream uses a different SEGB layout than `App.InFocus`. Records are protobuf entries with `0a <len> <ssid> 10 <connected_bool>` structure. Timestamps are embedded in the record metadata, not as standalone doubles.

```python
def parse_wifi_connections(filepath):
    """
    Parse Device.Wireless.WiFi SEGB file.
    Returns [(ssid, connected_bool), ...] in file order.
    """
    with open(filepath, 'rb') as f:
        data = f.read()

    if data[:4] != b'SEGB':
        return []

    events = []
    i = 32
    # Skip header padding
    while i < len(data) and data[i] == 0:
        i += 1

    while i < len(data) - 4:
        if data[i] == 0x0a:  # protobuf field 1, type string
            str_len = data[i + 1]
            if 2 < str_len < 60:
                try:
                    ssid = data[i + 2:i + 2 + str_len].decode('ascii')
                    if all(32 <= ord(c) < 127 for c in ssid) and any(c.isalpha() for c in ssid):
                        next_pos = i + 2 + str_len
                        connected = None
                        if next_pos < len(data) and data[next_pos] == 0x10:
                            connected = bool(data[next_pos + 1])
                        events.append((ssid, connected))
                        i = next_pos + 2
                        continue
                except (UnicodeDecodeError, IndexError):
                    pass
        i += 1

    return events
```

### Stream: Device.Wireless.Bluetooth

Records **connected/paired** Bluetooth devices — not nearby/scanned devices. Each event includes a MAC address and device name.

**Data per event:** MAC address, device name, connection state

**Cross-device:** This stream syncs across devices. iPhone Bluetooth connections (car, headphones) appear in `remote/{device-id}/`.

There is also a separate `Device.Wireless.BluetoothNearbyDevice` stream that records nearby BLE devices, but these are stored as anonymized UUIDs rather than readable names.

---

## Location

**The Biome `Location.*` streams are empty on Mac** — they only populate on iOS (which has GPS hardware) and do not sync via iCloud to the Mac. However, there are two good sources of location data accessible from macOS:

### Weather Location DB

The Weather app caches the device's **most recent** location with street-level precision in a SQLite database. This is a snapshot (single row), not a historical log — it reflects wherever the device was when Weather last refreshed.

```python
import sqlite3
import json
import os

def get_weather_location():
    """
    Get the most recent location from the Weather app cache.
    Returns dict with coordinates, place name, timezone.
    """
    db_path = os.path.expanduser("~/Library/Weather/current-location.db")
    if not os.path.exists(db_path):
        return None

    conn = sqlite3.connect(db_path)

    # Geocoded location has street-level name
    row = conn.execute("SELECT location, date FROM currentLocationGeocoded").fetchone()
    if row:
        loc = json.loads(row[0])
        return {
            'latitude': loc['coordinate']['latitude'],
            'longitude': loc['coordinate']['longitude'],
            'name': loc.get('name'),               # city (e.g. "Austin")
            'precise_name': loc.get('preciseName'), # street (e.g. "Gunter St")
            'timezone': loc.get('timeZone', {}).get('identifier'),
        }

    # Fallback to raw coordinates
    row = conn.execute("SELECT coordinate, date FROM currentLocationRaw").fetchone()
    if row:
        coord = json.loads(row[0])
        return {
            'latitude': coord['latitude'],
            'longitude': coord['longitude'],
        }

    conn.close()
    return None
```

**What you get:** City name, street name, precise lat/lng coordinates, timezone. Single row, overwritten each time Weather refreshes.

### WiFi SSIDs as Location Proxy

WiFi network names from `Device.Wireless.WiFi` are an indirect location signal. Different SSIDs correspond to different physical locations — home, office, coffee shops, hotels, etc.

```python
import glob, os
from collections import Counter

def get_wifi_networks():
    """
    Get all WiFi networks from Device.Wireless.WiFi stream.
    Returns [(ssid, connected_bool), ...] in chronological order.
    """
    base = os.path.expanduser(
        "~/Library/Biome/streams/restricted/Device.Wireless.WiFi/local"
    )
    all_events = []
    for filepath in glob.glob(os.path.join(base, "[0-9]*")):
        all_events.extend(parse_wifi_connections(filepath))
    return all_events


def wifi_location_summary():
    """Summarize locations by WiFi network frequency."""
    events = get_wifi_networks()
    counts = Counter(ssid for ssid, _ in events)
    return counts.most_common()
```

**What you get:** Every WiFi network the Mac has connected to, ordered by frequency. The most frequent SSID is likely home, the second most frequent is likely work/office. Note: this stream stores SSIDs and connection state but timestamps are encoded differently — use event ordering and frequency rather than absolute times.

### Location Permissions List

The location services clients.plist shows every app that has requested location access:

```bash
plutil -p /var/db/locationd/clients.plist
```

This is readable without root and shows app bundle IDs, paths, and authorization status.

---

### Stream: Notification.Usage

Records notification interactions — which app sent notifications, notification UUIDs.

**Data per event:** app bundle ID, notification UUID

---

### Stream: UserFocus.ComputedMode

Records Focus mode changes — Sleep, Do Not Disturb, custom focus modes.

**Data per event:** focus mode identifier (e.g., `com.apple.sleep.sleep-mode`), activation UUID

---

### Stream: App.DocumentInteraction

Records file opens with full file paths, file types, and which app opened them.

**Data per event:** full file path, file type (UTI), app bundle ID, bookmark data

---

### Stream: ScreenTime.AppUsage

A separate Screen Time-specific stream with app usage events. Similar to `App.InFocus` but structured for Screen Time's internal accounting.

---

## Full Stream Inventory

There are 100+ Biome streams. Here are the categories:

### App Activity
| Stream | What it records |
|--------|----------------|
| `App.InFocus` | Every foreground app switch (cross-device) |
| `App.WebUsage` | Website visits within apps |
| `App.WebApp.InFocus` | Web app foreground events |
| `App.DocumentInteraction` | Files opened, with paths and app |
| `App.Intent` | App intents and shortcuts triggered |
| `App.MediaUsage` | Media consumption per app |
| `App.MenuItem` | Menu item interactions |
| `App.Activity` | General app activity events |
| `ScreenTime.AppUsage` | Screen Time usage tracking |

### Media
| Stream | What it records |
|--------|----------------|
| `Media.NowPlaying` | Currently playing track, artist, album, source app (cross-device) |

### Communication
| Stream | What it records |
|--------|----------------|
| `Messages.Read` | Message read events (phone numbers) |
| `Siri.Remembers.MessageHistory` | Cross-device message context (cross-device) |
| `Siri.Remembers.CallHistory` | Cross-device call history (cross-device) |
| `Notification.Usage` | Notification interactions per app |
| `ProactiveHarvesting.Messages` | Message content for Siri intelligence |
| `ProactiveHarvesting.Mail` | Email content for Siri intelligence |

### Browsing
| Stream | What it records |
|--------|----------------|
| `Safari.Navigations` | Safari page navigations |
| `Safari.PageLoad` | Page load performance |
| `ProactiveHarvesting.Safari.PageView` | Safari browsing history for intelligence |

### Device State
| Stream | What it records |
|--------|----------------|
| `Device.Wireless.WiFi` | WiFi network connections (SSIDs) |
| `Device.Wireless.Bluetooth` | Bluetooth device connections (cross-device) |
| `Device.Power.LowPowerMode` | Low Power Mode toggles |
| `UserFocus.ComputedMode` | Focus mode changes (Sleep, DND, etc.) |
| `UserFocus.InferredMode` | System-inferred focus state |
| `GameController.Connected` | Game controller connections |

### Intelligence / AI
| Stream | What it records |
|--------|----------------|
| `AppleIntelligence.Availability` | Apple Intelligence feature availability |
| `GenerativeModels.GenerativeFunctions.Instrumentation` | On-device AI model usage |
| `IntelligencePlatform.EntityTagging.PersonInference` | Person entity inference |
| `Autonaming.Messages.Inferences` | Contact name inference from messages |
| `TextUnderstanding.Output.*` | Extracted entities (contacts, events, locations, links) |

### Location

**Note:** The Biome `Location.*` and `Motion.Activity` streams exist but are **empty on Mac** — they only populate on iOS devices (which have GPS) and do not sync to the Mac via iCloud. For location data accessible from macOS, see the [Location section](#location) above.

| Stream | What it records | On Mac? |
|--------|----------------|---------|
| `Location.Semantic` | Semantic location labels (home, work) | iOS only |
| `Location.HashedCoordinates` | Hashed GPS coordinates | iOS only |
| `Location.MicroLocationVisit` | Precise location visits | iOS only |
| `Location.PointOfInterest.Category` | POI categories visited | iOS only |
| `Motion.Activity` | Physical motion (walking, driving, stationary) | iOS only |

**Alternative location sources on Mac:**

| Source | What it provides |
|--------|-----------------|
| Weather DB (`~/Library/Weather/current-location.db`) | Current city, street, coordinates, timezone |
| `Device.Wireless.WiFi` stream | WiFi SSIDs with timestamps (location proxy) |
| `/var/db/locationd/clients.plist` | Apps with location access permissions |

### ProactiveHarvesting (Siri Intelligence)
| Stream | What it records | Typical size |
|--------|----------------|-------------|
| `ProactiveHarvesting.Safari.PageView` | Full browsing history | ~16MB |
| `ProactiveHarvesting.Messages` | Message content | ~16MB |
| `ProactiveHarvesting.Mail` | Email content | ~16MB |
| `ProactiveHarvesting.Notes` | Notes content | ~16MB |
| `ProactiveHarvesting.Reminders` | Reminder data | ~16MB |
| `ProactiveHarvesting.ThirdPartyApp` | Third-party app data | ~16MB |

These `ProactiveHarvesting` streams are large and contain rich text data that Apple Intelligence uses for suggestions and search. They're essentially a local cache of content from these apps.

---

## Cross-Device Streams

Not all streams sync across devices. These are the ones confirmed to have remote device data:

| Stream | Devices |
|--------|---------|
| `App.InFocus` | All iCloud-connected devices |
| `Media.NowPlaying` | All iCloud-connected devices |
| `Device.Wireless.Bluetooth` | Multiple devices |
| `Messages.SharedWithYou.Feedback` | Multiple devices |
| `Siri.Remembers.*` (all) | Multiple devices |

The `remote/{device-uuid}/` directory structure is the same across all streams.

---

## Accuracy Notes

- **Duration calculation** is approximate. We measure time between focus events, which closely matches Apple's Screen Time but may differ slightly.
- **Session cap** (default 1 hour) filters out overnight/idle gaps. Adjust based on use case — a movie app might need 3 hours.
- **Data retention:** Biome files rotate. Typically 2-4 weeks of data in remote streams. The Knowledge DB retains macOS data for months.
- **Missing data:** If "Share across devices" was recently enabled, only data generated after enabling sync will appear.
- **SEGB parsing** is pattern-based since the format isn't documented. The parsers here work reliably but may need adjustment if Apple changes the binary layout. Always validate output against known usage.

---

## How It Works (Technical Background)

### Knowledge DB (macOS only)

macOS tracks app usage in a CoreDuet Knowledge Store SQLite database. The `ZOBJECT` table stores events with:
- `ZSTREAMNAME = '/app/usage'` — foreground usage events
- `ZVALUESTRING` — bundle ID
- `ZSTARTDATE` / `ZENDDATE` — Core Data timestamps
- Joined to `ZSOURCE` for device ID info

### Biome Architecture

Biome is a distributed event store:
- **Local streams** (`local/`) — events from this device
- **Remote streams** (`remote/{device-id}/`) — synced from other iCloud devices
- **Sync DB** (`sync/sync.db`) — CloudKit sync metadata using CRDTs for conflict resolution

The SEGB binary format:
```
Offset  Size  Description
0       4     Magic: "SEGB"
4       28    Header (version, counts, flags)
32+     var   Entry records (variable-length protobuf with Core Data timestamps)
```

Each entry contains a 64-bit little-endian double (Core Data timestamp) followed by protobuf-encoded fields. The parsers scan for valid timestamps and extract nearby structured data (bundle IDs, URLs, strings).

**Why this works:** Even though Apple doesn't expose cross-device data through any public macOS API, the raw Biome data IS synced to the Mac for Siri intelligence and system features. We're reading the same underlying data that powers Screen Time's "All Devices" view.
