# Local Network Discovery — Skill for AI Agents

How to discover, identify, and probe devices on a user's local network. Use when the user asks about what's on their network, wants to find a device, needs a management URL, or wants to understand their home network topology.

---

## Quick Reference

| Tool | What it does | macOS | Linux |
|------|-------------|-------|-------|
| `arp -a` | List all known devices (IP + MAC) | Built-in | Built-in |
| `nmap` | Port scan, service detection, OS fingerprint | `brew install nmap` | `apt install nmap` |
| `dns-sd` | mDNS/Bonjour service discovery | Built-in | Use `avahi-browse` |
| SSDP (UDP multicast) | UPnP device discovery | Python script | Python script |
| `ipptool` | Printer IPP attributes | Built-in (CUPS) | `apt install cups-client` |

**Key insight:** ARP finds far more devices than nmap on a LAN. ARP operates at Layer 2 — devices MUST respond or they can't communicate. Nmap (without sudo) uses Layer 3/4 probes that IoT devices routinely ignore. Always start with ARP.

---

## Step 1: Discover All Devices (ARP)

ARP is the most reliable way to find everything on the local subnet.

```bash
# Populate ARP table by pinging broadcast address
ping -c 1 -t 1 192.168.1.255 2>/dev/null

# List all known devices
arp -a
```

Output format: `hostname (ip) at mac_address on interface ifscope [ethernet]`

To get the local subnet automatically:

```bash
# Get local IP and subnet
ifconfig en0 | grep 'inet '
# Typical output: inet 192.168.1.242 netmask 0xffffff00 broadcast 192.168.1.255

# Get default gateway
netstat -rn | grep default | head -1
```

### Parse ARP output to JSON

```bash
arp -a | python3 -c "
import sys, json, re
devices = []
for line in sys.stdin:
    m = re.match(r'(\S+)\s+\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+(\S+)\s+on\s+(\S+)', line)
    if m and m.group(3) != '(incomplete)':
        devices.append({
            'hostname': m.group(1) if m.group(1) != '?' else None,
            'ip': m.group(2),
            'mac': m.group(3),
            'interface': m.group(4)
        })
print(json.dumps(devices, indent=2))
"
```

---

## Step 2: Identify Vendors (MAC OUI Lookup)

The first 3 octets of a MAC address identify the manufacturer (OUI — Organizationally Unique Identifier).

### Option A: Local database (recommended)

Download the Wireshark manufacturer database (~2MB, ~35K entries):

```bash
curl -sL https://gitlab.com/wireshark/wireshark/-/raw/master/manuf -o /tmp/manuf.txt
```

Format: `PREFIX\tSHORT_NAME\tFULL_NAME` (tab-separated)

```bash
# Lookup a MAC address
mac="84:ea:ed:16:19:3a"
prefix=$(echo "$mac" | tr -d ':' | cut -c1-6 | tr '[:lower:]' '[:upper:]')
prefix_fmt="${prefix:0:2}:${prefix:2:2}:${prefix:4:2}"
grep -i "^$prefix_fmt" /tmp/manuf.txt
# Output: 84:EA:ED    Roku	Roku, Inc.
```

### Option B: REST API (maclookup.app — best free tier)

```bash
curl -s "https://api.maclookup.app/v2/macs/84:ea:ed:16:19:3a"
# {"success":true,"found":true,"macPrefix":"84EAED","company":"Roku, Inc.","country":"US",...}
```

Rate limits: 2 req/sec, 10K/day without key. 50 req/sec, 1M/day with free API key.

### Option C: macvendors.com (simplest)

```bash
curl -s "https://api.macvendors.com/84:ea:ed"
# Roku, Inc.
```

Rate limits: 1 req/sec, 1K/day. No API key needed.

### Common OUI prefixes for home devices

| Prefix | Vendor | Typical Devices |
|--------|--------|----------------|
| `FC:34:97` | ASUSTek | Routers, motherboards |
| `84:EA:ED` | Roku | Streaming devices |
| `E4:F0:42` | Google | Home/Nest speakers, Chromecast |
| `50:C2:E8` | Brother | Printers |
| `B8:27:EB`, `DC:A6:32` | Raspberry Pi | Pi boards |
| `00:17:88` | Philips Lighting | Hue bridge |
| `68:A4:0E` | Amazon | Echo, Fire TV |
| `F4:F5:D8` | Google | Nest Hub, newer Homes |
| `44:07:0B` | Google | Chromecast |
| `AC:84:C6` | TP-Link | Routers, smart plugs |
| `B0:BE:76` | TP-Link | Kasa smart devices |
| `70:B3:D5` | Various IoT | Common IoT range |

**Note on randomized MACs:** Modern phones/tablets use randomized (locally administered) MACs. The second hex digit of byte 1 will be `2`, `6`, `A`, or `E` (the "locally administered" bit is set). These won't match any vendor. Identify these devices by hostname instead.

---

## Step 3: Service Discovery (mDNS + SSDP)

### mDNS / Bonjour (dns-sd on macOS)

Devices advertise services via multicast DNS on `224.0.0.251:5353`.

```bash
# Browse for specific service types (each needs ~3-5 seconds)
timeout 5 dns-sd -B _http._tcp local.        # Web servers
timeout 5 dns-sd -B _ipp._tcp local.         # Printers (IPP)
timeout 5 dns-sd -B _ipps._tcp local.        # Printers (IPP over TLS)
timeout 5 dns-sd -B _googlecast._tcp local.  # Chromecast / Google Home
timeout 5 dns-sd -B _airplay._tcp local.     # AirPlay devices
timeout 5 dns-sd -B _raop._tcp local.        # AirPlay audio (Remote Audio Output)
timeout 5 dns-sd -B _homekit._tcp local.     # HomeKit accessories
timeout 5 dns-sd -B _ssh._tcp local.         # SSH servers
timeout 5 dns-sd -B _smb._tcp local.         # SMB file shares
timeout 5 dns-sd -B _afpovertcp._tcp local.  # AFP file shares (macOS)
timeout 5 dns-sd -B _roku._tcp local.        # Roku devices
timeout 5 dns-sd -B _hap._tcp local.         # HomeKit Accessory Protocol
timeout 5 dns-sd -B _companion-link._tcp local. # Apple devices
```

### SSDP / UPnP (Python)

Devices respond to UDP multicast M-SEARCH on `239.255.255.250:1900`.

```python
import socket, time

msg = (
    'M-SEARCH * HTTP/1.1\r\n'
    'HOST: 239.255.255.250:1900\r\n'
    'MAN: "ssdp:discover"\r\n'
    'MX: 3\r\n'
    'ST: ssdp:all\r\n'
    '\r\n'
).encode()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.settimeout(5)
sock.sendto(msg, ('239.255.255.250', 1900))

results = {}
end = time.time() + 5
while time.time() < end:
    try:
        data, addr = sock.recvfrom(4096)
        text = data.decode('utf-8', errors='replace')
        results.setdefault(addr[0], []).append(text)
    except socket.timeout:
        break

for ip, responses in sorted(results.items()):
    print(f"\n=== {ip} ({len(responses)} services) ===")
    for r in responses:
        for line in r.split('\r\n'):
            if line.upper().startswith(('SERVER:', 'ST:', 'LOCATION:', 'USN:')):
                print(f"  {line}")
```

**Key SSDP fields:**
- `LOCATION:` — URL to device description XML (manufacturer, model, serial number)
- `SERVER:` — UPnP stack version and device firmware
- `ST:` — Service type (e.g., `roku:ecp`, `upnp:rootdevice`)
- `USN:` — Unique Service Name (device UUID)

**Follow up LOCATION URLs** to get rich device info:

```bash
curl -s http://192.168.1.1:47229/rootDesc.xml  # Router UPnP description
curl -s http://192.168.1.246:8060/dial/dd.xml   # Roku DIAL description
```

---

## Step 4: Device-Specific APIs (Unauthenticated)

Many devices expose rich APIs on the LAN without authentication.

### Roku (Port 8060 — External Control Protocol)

Roku devices expose everything via ECP. This is the gold standard for unauthenticated device APIs.

```bash
# Full device info (serial, model, firmware, MACs, location, timezone, etc.)
curl -s http://{ip}:8060/query/device-info

# Installed apps/channels
curl -s http://{ip}:8060/query/apps

# Currently running app
curl -s http://{ip}:8060/query/active-app

# App icons
curl -s http://{ip}:8060/query/icon/{app_id} > icon.png
```

Returns XML. Key fields from `/query/device-info`:
- `<model-name>`, `<model-number>`, `<serial-number>`
- `<software-version>`, `<build-number>`
- `<wifi-mac>`, `<ethernet-mac>`, `<bluetooth-mac>`
- `<network-name>` (SSID), `<network-type>`
- `<user-device-name>`, `<user-device-location>`
- `<uptime>` (seconds), `<power-mode>`
- `<supports-airplay>`, `<supports-find-remote>`

**Note:** If `<ecp-setting-mode>` is `limited`, some endpoints (like `/query/apps`) may be restricted.

### Google Home / Chromecast (Port 8443)

```bash
# Device info (name, build, signal, WiFi, uptime)
curl -sk https://{ip}:8443/setup/eureka_info
```

Returns JSON. Key fields:
- `name` — friendly name (user-assigned device name)
- `build_version`, `cast_build_revision`
- `ip_address`, `mac_address`
- `ssid`, `signal_level` (dBm), `noise_level` (dBm)
- `uptime` (seconds)
- `locale`, `timezone`

**Note:** Most endpoints beyond `eureka_info` now require a `cast-local-authorization-token` (since 2019). The mDNS TXT records for `_googlecast._tcp` also contain model (`md=`) and friendly name (`fn=`).

### Printers (IPP — Port 631)

```bash
# Full printer attributes (model, capabilities, status, supply levels)
ipptool -tv ipp://{ip}/ipp/print get-printer-attributes.test 2>&1

# Or discover and list all printers
ippfind --ls
```

Key IPP attributes:
- `printer-make-and-model` — "Brother HL-L3270CDW series"
- `printer-state` — idle, processing, stopped
- `printer-state-reasons` — none, toner-low, paper-empty, etc.
- `media-supported` — paper sizes
- `print-color-mode-supported` — color, monochrome
- `sides-supported` — one-sided, two-sided-long-edge
- `printer-resolution-supported` — e.g., 600dpi

Many printers also expose HTTP management on port 80/443 (web admin interface).

### ASUS Routers (Port 80)

ASUS routers running AsusWRT expose a web admin on port 80. The login page itself reveals the model. Authentication required for everything useful.

```bash
curl -s http://{ip}/ | head -20
# Typically redirects to /Main_Login.asp
# HTTP headers reveal: Server: httpd/2.0
```

The UPnP description (via SSDP LOCATION URL) reveals more:
- Server string: `AsusWRT/386 UPnP/1.1 MiniUPnPd/2.2.0`
- Full device description XML with model name

### Samsung Smart TVs (Port 8001/8002)

```bash
# Older models (HTTP)
curl -s http://{ip}:8001/api/v2/
# Newer models (WSS) — just the info endpoint still works over HTTP
curl -s http://{ip}:8001/api/v2/
```

Returns device info JSON if the TV is on.

---

## Step 5: Port Scanning (nmap)

```bash
# Quick scan — top 20 ports on all devices
nmap -sV --top-ports 20 192.168.1.0/24

# Detailed scan — specific device, top 1000 ports
nmap -sV --top-ports 1000 192.168.1.246

# With sudo — OS detection + ARP-based discovery (much better results)
sudo nmap -sV -O -sn 192.168.1.0/24          # Ping scan with OS hints
sudo nmap -sV -O --top-ports 100 192.168.1.1  # Detailed with OS detection
```

**Without sudo:** nmap can't use raw sockets on macOS, so host discovery falls back to TCP/ICMP probes (many IoT devices ignore these). Service detection (`-sV`) still works on discovered hosts.

**With sudo:** nmap uses ARP for host discovery (finds everything) and can do OS fingerprinting (`-O`).

### Common ports on home network devices

| Port | Protocol | Service | Typical Devices |
|------|----------|---------|-----------------|
| 22 | TCP | SSH | Linux boxes, Raspberry Pi, NAS |
| 53 | TCP/UDP | DNS | Routers, Pi-hole |
| 80 | TCP | HTTP | Routers, printers, cameras, NAS |
| 443 | TCP | HTTPS | Same as 80, with TLS |
| 515 | TCP | LPD | Printers |
| 548 | TCP | AFP | macOS file sharing |
| 631 | TCP | IPP | Printers (CUPS) |
| 1900 | UDP | SSDP | UPnP devices |
| 5000 | TCP | Synology DSM | Synology NAS |
| 5353 | UDP | mDNS | Bonjour/Avahi devices |
| 7000 | TCP | AirPlay | Apple TV, AirPlay speakers |
| 8008 | TCP | HTTP Alt | Chromecast |
| 8060 | TCP | Roku ECP | Roku devices |
| 8080 | TCP | HTTP Alt | Various web UIs |
| 8443 | TCP | HTTPS Alt | Chromecast setup |
| 9100 | TCP | JetDirect | Printers (raw) |
| 32400 | TCP | Plex | Plex Media Server |
| 49152+ | TCP | UPnP | Dynamic UPnP ports |

---

## Step 6: Default Credentials Lookup

The SecLists project (MIT-licensed) maintains a CSV of default credentials by vendor:

```bash
# Download the default credentials database
curl -sL https://raw.githubusercontent.com/danielmiessler/SecLists/master/Passwords/Default-Credentials/default-passwords.csv -o /tmp/default-passwords.csv

# Look up by vendor
grep -i "brother" /tmp/default-passwords.csv
grep -i "asus" /tmp/default-passwords.csv
grep -i "roku" /tmp/default-passwords.csv
```

CSV format: `vendor,username,password`

These are manufacturer-published default credentials — public information that device owners should know about (and change).

---

## Entity Design

Network discovery maps to four entity types in the AgentOS primitive system.

### The Apartment Building Metaphor

A device is an **apartment building**. It has:
- A **MAC address** — its digital identity (like a passport number). Permanent, burned in at manufacture.
- An **IP address** — its street address on the network. Can change (DHCP = moving to a new address).
- **Ports** — rooms/doors inside the building. Port 80 is the front door, port 22 is the back door, port 631 is the service entrance.
- **Services** — what you find when you walk through a door/room.

This maps directly to how physical places work:

```
Physical:  neighborhood → street_address → building → room → what's inside
Digital:   network      → ip_address     → device   → port → service
```

### What's a place, what's an identity, what's a record?

| Concept | Primitive | Reasoning |
|---------|-----------|-----------|
| **Network** (subnet) | **place** | Where devices exist. "What's on this network?" |
| **IP address** | **place** | Where a device lives. You navigate *to* it. DHCP change = moving. |
| **Device** | **place** | The apartment building. Where services run. |
| **MAC address** | **identifier** (property on device) | A digital passport. Not a location — an identity. You don't navigate to a MAC address. |
| **Service** | **record** | Data that was recorded about what's running at a port. |
| **Port** | property on service (round 1) | Rooms inside the building. Could become its own place entity later. |

The key distinction: **addresses are places, identities are properties.** An IP address is where you go (place). A MAC address is who you are (identity). Same as: a street address is a place, a passport number is a property on a person.

### `network` extends `place`

A network is **where IP addresses and devices exist**. "What's on this network?" = "What's at this place?"

```yaml
id: network
plural: networks
extends: place
name: Network
description: A local network segment — where devices exist

properties:
  # Inherits from place: id, name, description, url
  subnet:
    type: string
    description: CIDR notation (e.g., 192.168.1.0/24)
  gateway_ip:
    type: string
    format: ip
  ssid:
    type: string
    description: WiFi network name (if applicable)
  network_type:
    type: string
    enum: [wifi, ethernet, vpn, bridge, unknown]

identifiers: [subnet, ssid]
actions: [list, get, search]

display:
  primary: name
  secondary: subnet
  icon: network
```

### `ip_address` extends `place`

An IP address is a **street address on the network**. Devices live at IP addresses. When DHCP assigns a new IP, the device moves — same temporal pattern as a person moving to a new city.

```yaml
id: ip_address
plural: ip_addresses
extends: place
name: IP Address
description: A network address — where a device lives on the network

properties:
  # Inherits from place: id, name, description, url
  address:
    type: string
    format: ip
    required: true
    description: The IP address (e.g., 192.168.1.246)
  version:
    type: string
    enum: [ipv4, ipv6]
  assignment:
    type: string
    enum: [static, dhcp, self_assigned, unknown]

identifiers: [address]
actions: [list, get, search]

display:
  primary: address
  secondary: assignment
  icon: map-pin
```

**Temporal model (DHCP = moving):**

```
# Device gets assigned an IP (moves to a new address)
device:"Roku Ultra" --move_to--> ip_address:"192.168.1.246"  (Monday)

# DHCP lease changes
device:"Roku Ultra" --move_to--> ip_address:"192.168.1.100"  (Thursday)

# Query: "Where is the Roku?" → latest move_to = 192.168.1.100
# Query: "What was at .246 last Monday?" → the Roku (historical traversal)
# Query: "What IPs has the Roku had?" → replay all move_to actions
```

Same pattern as `person --move_to--> city` in the place spec. No special mechanism needed — the temporal action model handles it.

**IP addresses live in networks:**

```
ip_address:"192.168.1.246" --add_to--> network:"Home WiFi" (192.168.1.0/24)
ip_address:"192.168.1.100" --add_to--> network:"Home WiFi"
```

### `device` extends `place`

A device is **where services run** — the apartment building. "What services are on this device?" = "What's at this place?" The hardware/product nature is expressed through graph edges, not the type (roles are relationships, not types).

The device's MAC address is its **digital identity** — like a passport number or national ID. Permanent (burned into hardware), used for identification, not navigation.

```yaml
id: device
plural: devices
extends: place
name: Device
description: A device on a network — the apartment building where services run

properties:
  # Inherits from place: id, name, description, url
  hostname:
    type: string
    description: mDNS or DHCP hostname
  device_type:
    type: string
    enum: [router, switch, access_point, printer, computer, phone, tablet,
           smart_speaker, streaming_device, tv, camera, thermostat,
           light, appliance, game_console, nas, wearable, unknown]
  vendor:
    type: string
    description: Manufacturer from MAC OUI lookup
  model:
    type: string
  model_number:
    type: string
  serial_number:
    type: string
  firmware_version:
    type: string
  mac_address:
    type: string
    description: Primary MAC — the device's digital identity (like a passport number)
  additional_macs:
    type: array
    items:
      type: object
      properties:
        type: { type: string, enum: [wifi, ethernet, bluetooth] }
        address: { type: string }
  status:
    type: string
    enum: [online, offline, suspended, unknown]
  last_seen:
    type: datetime
  uptime:
    type: integer
    description: Seconds
  network_type:
    type: string
    enum: [wifi, ethernet, unknown]
  ssid:
    type: string
    description: WiFi network name if applicable
  signal_strength:
    type: integer
    description: dBm (negative number, closer to 0 = stronger)
  management_url:
    type: string
    format: url
    description: URL to device's web admin interface
  default_credentials:
    type: object
    properties:
      username: { type: string }
      password: { type: string }
      source: { type: string }
    description: Manufacturer-published default credentials (public information)
  location:
    type: string
    description: Physical location from device API or user (e.g., "Living room")
  discovery_methods:
    type: array
    items:
      type: string
    description: How this device was found (arp, mdns, ssdp, nmap, roku_ecp, etc.)
  data:
    type: object
    description: Device-specific data (Roku apps, printer capabilities, cast info, etc.)

identifiers:
  - mac_address
  - serial_number

actions: [list, get, search]

display:
  primary: name
  secondary: device_type
  status: status
  icon: router
  sort:
    - field: name
      order: asc
```

Note: `ip_address` is no longer in identifiers — it's a separate place entity that the device `move_to`'s. The device's stable identifiers are MAC address (digital ID) and serial number.

### `service` extends `record`

A service is **data that was recorded** about what's running on a device. "Port 80 is open running nginx 1.24" is an observation — recorded data, same as a DNS record on a domain.

The port number is a property on the service for now. In the apartment building metaphor, the port is the *room* the service was found in. If ports ever need their own graph edges (e.g., "what was running on port 80 over time?"), they could graduate to their own place entity (rooms inside the building).

```yaml
id: service
plural: services
extends: record
name: Service
description: A network service discovered running on a device

properties:
  # Inherits from record: id, name, type, value
  protocol:
    type: string
    enum: [tcp, udp]
  port:
    type: integer
    description: The port (room number) this service was found on
  version:
    type: string
    description: Service version string from banner/probe
  banner:
    type: string
    description: Raw service banner
  url:
    type: string
    format: url
    description: Access URL if applicable (e.g., http://192.168.1.161:631/)
  status:
    type: string
    enum: [open, closed, filtered]

identifiers:
  - port
  - protocol

actions: [list, get, search]

display:
  primary: name
  secondary: port
  icon: activity
```

### Graph structure

```
network:"Home WiFi" (place)
  ├── ip_address:"192.168.1.1" (place) — added to network
  │     └── device:"ASUS Router" (place) — move_to this address
  │           ├── service:DNS (record) — port 53
  │           ├── service:HTTP (record) — port 80, management_url
  │           └── service:UPnP (record) — port 49152
  │
  ├── ip_address:"192.168.1.161" (place)
  │     └── device:"Brother Printer" (place) — move_to this address
  │           ├── service:HTTP (record) — port 80
  │           ├── service:IPP (record) — port 631
  │           └── service:JetDirect (record) — port 9100
  │
  ├── ip_address:"192.168.1.246" (place)
  │     └── device:"Roku Ultra" (place) — move_to this address
  │           └── service:"Roku ECP" (record) — port 8060
  │
  └── ...
```

Actions follow the "no passive states" principle:
- `scanner --add_to--> ip_address → network` — address exists in this network
- `device --move_to--> ip_address` — device lives at this address (DHCP assignment)
- `scanner --add_to--> service → device` — service discovered on device
- The scanner is an `agent` (extends actor) performing `claim` actions

---

## Adapter Design

The adapter uses the `command:` executor (same pattern as the YouTube/yt-dlp adapter) to run local scanning tools and map output to entities.

```yaml
id: local-network
name: Local Network
description: Discover and monitor devices on your local network
icon: network
category: infrastructure

requires:
  - name: nmap
    install:
      macos: brew install nmap
      linux: sudo apt install -y nmap
  # arp is built-in on macOS and Linux
  # dns-sd is built-in on macOS; Linux uses avahi-browse

entities: [device, service, network]
```

### Scanning approach (layered)

```
Layer 1: ARP scan → IP + MAC for every device on subnet
Layer 2: MAC OUI lookup → vendor name (local Wireshark manuf DB)
Layer 3: Parallel discovery probes:
  ├── mDNS browse (common service types) → hostnames, services, metadata
  ├── SSDP M-SEARCH → UPnP device descriptions (manufacturer, model, serial)
  └── Device-specific API probes:
      ├── :8060 → Roku ECP (serial, model, firmware, apps, location)
      ├── :8443 → Chromecast (name, build, signal, noise)
      ├── :631  → IPP (model, capabilities, status, supply levels)
      ├── :80/443 → HTTP header + HTML title (router model, banner)
      └── :22   → SSH banner
Layer 4: Merge all signals per MAC address into unified device entity
Layer 5: Cross-reference with SecLists default credentials
```

### Operations sketch

```yaml
operations:
  device.list:
    description: Discover all devices on the local network
    returns: device[]
    params:
      subnet: { type: string, description: "CIDR (default: auto-detect)" }
    command:
      binary: bash
      args: ["-l", "-c", "..."]  # ARP + OUI + mDNS + SSDP merge script
      timeout: 60

  device.get:
    description: Deep probe a specific device
    returns: device
    params:
      ip: { type: string, required: true }
    command:
      binary: bash
      args: ["-l", "-c", "..."]  # nmap + device-specific APIs
      timeout: 90

  service.list:
    description: List services running on a device
    returns: service[]
    params:
      ip: { type: string, required: true }
    command:
      binary: bash
      args: ["-l", "-c", "..."]  # nmap -sV on target
      timeout: 120
```

---

## Maltego Comparison

Maltego is the industry standard for graph-based network/infrastructure visualization. Key lessons:

### Entity mapping (Maltego → AgentOS)

| Maltego Entity | AgentOS Primitive | AgentOS Type | Notes |
|----------------|------------------|--------------|-------|
| Domain | work | `domain` | Already exists |
| DNS Name / MXRecord / NSRecord | record | `dns_record` (with type field) | Already exists. We use one entity with a type discriminator, not separate types per record type. Cleaner than Maltego's approach. |
| IPv4Address | place | `ip_address` | An IP address is a street address on the network. Devices `move_to` IP addresses (DHCP = moving). |
| Netblock / CIDR | place | `network` | A netblock is where IPs live — that's a place. |
| Port | record | Property on service | Port is a service property for round 1. Could become a place ("room in the building") later. |
| Service | record | `service` | Running service instance = recorded data. |
| Website | place | `channel` or future `website` | A website is a place — content lives there. |
| Location | place | `city` / `country` / `venue` | Already exists. |
| Person | actor | `person` | Already exists. |
| Organization | actor | `organization` | Already exists. |
| CVE | record | Future `vulnerability` | A CVE is recorded vulnerability data. |
| SSL Certificate | declaration | Future `certificate` | A CA *declares* trust — saying it makes it so. |
| Banner | record | Property on service | Not standalone — it's a service property. |

### Where AgentOS goes beyond Maltego

1. **Named, typed relationships.** Maltego just has "transform connected A to B." We know WHY things are connected (which action, which actor, when).
2. **Temporal model.** Maltego graphs are snapshots. We have full action history. "When did this service appear?" is answerable.
3. **Actor attribution.** We always know who/what discovered each fact.
4. **Local network scanning.** Maltego has NO built-in local scanning — users write custom Python transforms. We have it as a first-class adapter.
5. **Unified physical + digital.** Maltego keeps network topology separate from physical locations. Our `place` primitive unifies both substrates.

---

## Data Sources Reference

| Source | Type | Cost | What It Gives |
|--------|------|------|---------------|
| ARP table | Local command | Free | All IP/MAC pairs on subnet |
| Wireshark manuf DB | Local file (~2MB) | Free | MAC → vendor name (35K entries) |
| maclookup.app | REST API | Free (1M/day with key) | MAC → vendor + country |
| macvendors.com | REST API | Free (1K/day) | MAC → vendor name |
| IEEE OUI database | Download | Free | Official MAC → organization |
| mDNS / Bonjour | Multicast protocol | Free | Hostnames, services, TXT metadata |
| SSDP / UPnP | Multicast protocol | Free | Device descriptions (manufacturer, model, serial) |
| Roku ECP | Local HTTP (:8060) | Free | Full Roku device info, apps, playback |
| Chromecast API | Local HTTPS (:8443) | Free | Name, build, signal, WiFi info |
| IPP | Local protocol (:631) | Free | Printer model, capabilities, status |
| nmap | Local tool | Free | Open ports, service versions, OS fingerprinting |
| SecLists | GitHub CSV (MIT) | Free | Default credentials by vendor (~3K entries) |
| Fingerbank | REST API | Free tier | DHCP fingerprint → device identification |

---

## Mountable Drives (Future)

Devices with certain services could be exposed as drives in AgentOS:

| Service | Protocol | Mount Method |
|---------|----------|-------------|
| SSH (port 22) | SFTP | `sshfs` or native SFTP |
| SMB (port 445) | SMB/CIFS | `mount_smbfs` on macOS |
| AFP (port 548) | AFP | `mount_afp` on macOS |
| FTP (port 21) | FTP | Various |
| NFS (port 2049) | NFS | `mount_nfs` |

If a device has SSH, it could automatically generate a drive entity for SFTP access. Printers with scan-to-folder could expose scan directories.

---

## Tips

- **Always start with ARP**, not nmap. ARP is mandatory at Layer 2; nmap probes are optional at Layer 3/4.
- **Randomized MACs** (phones, tablets) won't match vendor databases. Identify by hostname instead.
- **IoT devices drop TCP probes.** Google Home, Roku (suspended), smart speakers often ignore nmap. Use mDNS and SSDP for these.
- **sudo nmap** is dramatically better than regular nmap on macOS. It enables ARP-based discovery and OS fingerprinting.
- **Device-specific APIs** (Roku ECP, Chromecast, IPP) give richer data than any scanning tool. Probe known ports after initial discovery.
- **SSDP LOCATION URLs** contain XML with manufacturer, model, and serial. Always follow these up.
- **mDNS TXT records** often contain model info, firmware version, and capabilities. Resolve services, don't just browse them.
