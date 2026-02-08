---
id: facebook
name: Facebook
description: Query public Facebook group information without login
icon: icon.png
color: "#106BFF"

website: https://facebook.com
privacy_url: https://www.facebook.com/privacy/policy
terms_url: https://www.facebook.com/legal/terms

requires:
  - name: Chromium
    install:
      macos: brew install --cask chromium
      linux: sudo apt install -y chromium-browser
      windows: choco install chromium -y

instructions: |
  Facebook-specific notes:
  - Works for public groups only (no login required)
  - Uses curl for metadata (fast, ~100ms)
  - Uses Chromium headless --dump-dom for member count (slower, ~2-3s)
  - Group must be public for this to work
  - If Chromium not installed, member_count will be null

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
  community:
    terminology: Group
    mapping:
      id: .id
      name: .name
      description: .description
      url: .url
      icon: .icon
      member_count: .member_count_raw
      member_count_numeric: .member_count_numeric
      privacy: .privacy

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  community.get:
    description: Get metadata for a public Facebook group
    returns: community
    params:
      group:
        type: string
        required: true
        description: "Group name or URL (e.g., 'becomingaportuguesecitizen' or full URL)"
      include_members:
        type: boolean
        default: true
        description: "Include member count (requires Chromium, slower ~2-3s)"
    command:
      binary: bash
      args:
        - "-c"
        - |
          set -e
          GROUP_PARAM="{{params.group}}"
          INCLUDE_MEMBERS="{{params.include_members | default:true}}"
          
          # Extract group name/ID from parameter
          # Handle: "becomingaportuguesecitizen", "23386646249", or full URL
          if [[ "$GROUP_PARAM" == *"facebook.com/groups/"* ]]; then
            GROUP_NAME=$(echo "$GROUP_PARAM" | sed -E 's|.*facebook.com/groups/([^/]+).*|\1|')
          else
            GROUP_NAME="$GROUP_PARAM"
          fi
          
          GROUP_URL="https://www.facebook.com/groups/$GROUP_NAME/"
          
          # Step 1: Fetch og meta tags with curl (fast)
          HTML=$(curl -sL -H "User-Agent: Mozilla/5.0" "$GROUP_URL" 2>/dev/null || echo "")
          
          if [ -z "$HTML" ]; then
            echo '{"error": "Failed to fetch group page. Group may be private or not found."}'
            exit 1
          fi
          
          # Extract group ID from al:ios:url or al:android:url
          GROUP_ID=$(echo "$HTML" | grep -oE 'fb://group/[0-9]+' | head -1 | sed 's|fb://group/||' || echo "")
          
          # Extract og:title (e.g., "Becoming a Portuguese Citizen | Facebook")
          TITLE=$(echo "$HTML" | grep -oE '<meta[^>]*property="og:title"[^>]*content="([^"]+)"' | sed -E 's/.*content="([^"]+)".*/\1/' | sed 's/ | Facebook$//' || echo "")
          
          # Extract og:description
          DESCRIPTION=$(echo "$HTML" | grep -oE '<meta[^>]*property="og:description"[^>]*content="([^"]+)"' | sed -E 's/.*content="([^"]+)".*/\1/' || echo "")
          
          # Extract og:image (group cover/icon)
          OG_IMAGE=$(echo "$HTML" | grep -oE '<meta[^>]*property="og:image"[^>]*content="([^"]+)"' | sed -E 's/.*content="([^"]+)".*/\1/' || echo "")
          
          # Step 2: Get member count with Chromium (if requested and available)
          MEMBER_COUNT_RAW=""
          MEMBER_COUNT_NUMERIC=""
          
          if [ "$INCLUDE_MEMBERS" = "true" ]; then
            # Check if Chromium is available
            CHROMIUM_PATH=""
            if command -v chromium >/dev/null 2>&1; then
              CHROMIUM_PATH="chromium"
            elif [ -f "/Applications/Chromium.app/Contents/MacOS/Chromium" ]; then
              CHROMIUM_PATH="/Applications/Chromium.app/Contents/MacOS/Chromium"
            elif command -v chromium-browser >/dev/null 2>&1; then
              CHROMIUM_PATH="chromium-browser"
            fi
            
            if [ -n "$CHROMIUM_PATH" ]; then
              # Use Chromium to get rendered DOM
              DOM=$("$CHROMIUM_PATH" --headless --dump-dom "$GROUP_URL" 2>/dev/null || echo "")
              
              if [ -n "$DOM" ]; then
                # Extract member count (e.g., "2.3K members" or "78,000 members")
                MEMBER_COUNT_RAW=$(echo "$DOM" | grep -oE '[0-9,.]+K?\s*members?' | head -1 | sed 's/\s*members\?//' || echo "")
                
                # Parse to integer
                if [ -n "$MEMBER_COUNT_RAW" ]; then
                  # Remove commas
                  CLEANED=$(echo "$MEMBER_COUNT_RAW" | tr -d ',')
                  
                  # Handle K suffix (×1000)
                  if [[ "$CLEANED" == *K ]]; then
                    NUM=$(echo "$CLEANED" | sed 's/K//' | awk '{printf "%.0f", $1 * 1000}')
                    MEMBER_COUNT_NUMERIC="$NUM"
                  # Handle M suffix (×1,000,000)
                  elif [[ "$CLEANED" == *M ]]; then
                    NUM=$(echo "$CLEANED" | sed 's/M//' | awk '{printf "%.0f", $1 * 1000000}')
                    MEMBER_COUNT_NUMERIC="$NUM"
                  # Plain number
                  elif [[ "$CLEANED" =~ ^[0-9]+$ ]]; then
                    MEMBER_COUNT_NUMERIC="$CLEANED"
                  fi
                fi
              fi
            fi
          fi
          
          # Determine privacy (default to OPEN for public groups)
          PRIVACY="OPEN"
          
          # Output JSON
          jq -n \
            --arg id "$GROUP_ID" \
            --arg name "$TITLE" \
            --arg description "$DESCRIPTION" \
            --arg url "$GROUP_URL" \
            --arg icon "$OG_IMAGE" \
            --arg member_count_raw "$MEMBER_COUNT_RAW" \
            --argjson member_count_numeric "${MEMBER_COUNT_NUMERIC:-null}" \
            --arg privacy "$PRIVACY" \
            '{
              id: $id,
              name: $name,
              description: $description,
              url: $url,
              icon: $icon,
              member_count_raw: $member_count_raw,
              member_count_numeric: $member_count_numeric,
              privacy: $privacy
            }'
      timeout: 35

---

# Facebook

Query public Facebook group information without requiring login.

## How It Works

Uses two methods that work without authentication:

### 1. Get Group Metadata (curl)

Public og meta tags are accessible via simple HTTP request:

```bash
curl -s -L -H "User-Agent: Mozilla/5.0" "https://www.facebook.com/groups/GROUP_NAME/" 2>/dev/null
```

**Returns:**
- **Group ID**: From `fb://group/520427849972613` in `al:ios:url` or `al:android:url`
- **Group name**: `og:title` (e.g., "Becoming a Portuguese Citizen | Facebook")
- **Description**: `og:description` (group's about text)

### 2. Get Member Count (Chromium headless)

Member count is loaded via JavaScript, so need headless browser:

```bash
/Applications/Chromium.app/Contents/MacOS/Chromium --headless --dump-dom "https://www.facebook.com/groups/GROUP_NAME/" 2>/dev/null | grep -oE '[0-9,.]+K?\s*members?' | head -1
```

**Returns:** Member count like `2.3K members` or `78,000 members`

## Why This Works

- **curl** can get public og meta tags (title, description, group ID) without login
- **Chromium --dump-dom** renders JavaScript and dumps the final DOM, which includes the dynamically-loaded member count
- Regular curl fails for member count because Facebook loads it via JavaScript

## Implementation Notes

- Use `command` executor with bash script
- Parse og meta tags with grep/sed
- Chromium headless is slower (~2-3s) but required for member count
- Could add `include_members: false` param to skip the slow headless call
- Group must be public for this to work
- Consider caching results since group info doesn't change often

## Examples

```bash
# Portuguese citizenship group
POST /api/adapters/facebook/group.get
{"group": "becomingaportuguesecitizen"}
# → { id: "...", name: "Becoming a Portuguese Citizen", member_count: "2.3K", ... }

# Italian jure sanguinis group (by ID)
POST /api/adapters/facebook/group.get
{"group": "23386646249"}
# → { id: "23386646249", name: "...", member_count: "78,000", ... }
```

## Future Extensions

- `group.search`: Search for groups by keyword (would need different approach)
- `post.list`: Get recent public posts from a group (may require login)
- Authenticated actions via Playwright (like Instagram connector)

## References

- Linear task AGE-288: Facebook Connector: Groups API (no login required)
- Found in Cursor transcript: `/Users/joe/.cursor/projects/Users-joe-dev-adavia-marketing/agent-transcripts/7a69f4bc-4dbb-4666-b706-31d672c48206.txt`
