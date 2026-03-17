#!/usr/bin/env bash
set -euo pipefail

GROUP_PARAM="${1:-}"
INCLUDE_MEMBERS="${2:-true}"

if [[ "$GROUP_PARAM" == *"facebook.com/groups/"* ]]; then
  GROUP_NAME=$(echo "$GROUP_PARAM" | sed -E 's|.*facebook.com/groups/([^/]+).*|\1|')
else
  GROUP_NAME="$GROUP_PARAM"
fi

GROUP_URL="https://www.facebook.com/groups/$GROUP_NAME/"

HTML=$(curl -sL -H "User-Agent: Mozilla/5.0" "$GROUP_URL" 2>/dev/null || echo "")
if [ -z "$HTML" ]; then
  echo '{"error":"Failed to fetch group page. Group may be private or not found."}'
  exit 1
fi

GROUP_ID=$(echo "$HTML" | grep -oE 'fb://group/[0-9]+' | awk 'NR==1{gsub("fb://group/",""); print}' || echo "")
TITLE=$(echo "$HTML" | grep -oE '<meta[^>]*property="og:title"[^>]*content="([^"]+)"' | sed -E 's/.*content="([^"]+)".*/\1/' | sed 's/ | Facebook$//' || echo "")
DESCRIPTION=$(echo "$HTML" | grep -oE '<meta[^>]*property="og:description"[^>]*content="([^"]+)"' | sed -E 's/.*content="([^"]+)".*/\1/' || echo "")
OG_IMAGE=$(echo "$HTML" | grep -oE '<meta[^>]*property="og:image"[^>]*content="([^"]+)"' | sed -E 's/.*content="([^"]+)".*/\1/' || echo "")

MEMBER_COUNT_RAW=""
MEMBER_COUNT_NUMERIC="null"

if [ "$INCLUDE_MEMBERS" = "true" ]; then
  CHROMIUM_PATH=""
  if command -v chromium >/dev/null 2>&1; then
    CHROMIUM_PATH="chromium"
  elif [ -f "/Applications/Chromium.app/Contents/MacOS/Chromium" ]; then
    CHROMIUM_PATH="/Applications/Chromium.app/Contents/MacOS/Chromium"
  elif command -v chromium-browser >/dev/null 2>&1; then
    CHROMIUM_PATH="chromium-browser"
  fi

  if [ -n "$CHROMIUM_PATH" ]; then
    DOM=$("$CHROMIUM_PATH" --headless --dump-dom "$GROUP_URL" 2>/dev/null || echo "")
    if [ -n "$DOM" ]; then
      MEMBER_COUNT_RAW=$(echo "$DOM" | grep -oE '[0-9,.]+K?\s*members?' | awk 'NR==1{sub(/\s*members?/,""); print}' || echo "")
      if [ -n "$MEMBER_COUNT_RAW" ]; then
        CLEANED=$(echo "$MEMBER_COUNT_RAW" | tr -d ',')
        if [[ "$CLEANED" == *K ]]; then
          MEMBER_COUNT_NUMERIC=$(echo "$CLEANED" | sed 's/K//' | awk '{printf "%.0f", $1 * 1000}')
        elif [[ "$CLEANED" == *M ]]; then
          MEMBER_COUNT_NUMERIC=$(echo "$CLEANED" | sed 's/M//' | awk '{printf "%.0f", $1 * 1000000}')
        elif [[ "$CLEANED" =~ ^[0-9]+$ ]]; then
          MEMBER_COUNT_NUMERIC="$CLEANED"
        fi
      fi
    fi
  fi
fi

jq -n \
  --arg id "$GROUP_ID" \
  --arg name "$TITLE" \
  --arg description "$DESCRIPTION" \
  --arg url "$GROUP_URL" \
  --arg icon "$OG_IMAGE" \
  --arg member_count_raw "$MEMBER_COUNT_RAW" \
  --argjson member_count_numeric "$MEMBER_COUNT_NUMERIC" \
  --arg privacy "OPEN" \
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
