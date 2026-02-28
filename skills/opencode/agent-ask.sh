#!/bin/bash
set -euo pipefail

BASE_URL="${AGENTOS_URL:-http://127.0.0.1:3456}"
PROJECT_NAME="$1"
QUESTION="$2"
MODEL="${3:-}"

# 1. Search Memex for the project by name
SEARCH_RESULT=$(curl -sf -X POST "$BASE_URL/mem/search" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$PROJECT_NAME\", \"types\": [\"project\"], \"limit\": 5}" 2>/dev/null)

if [ -z "$SEARCH_RESULT" ]; then
  echo '{"error": "Failed to search Memex for project"}'
  exit 0
fi

# Find best matching project (first result from search)
PROJECT_ID=$(echo "$SEARCH_RESULT" | jq -r '.data[0]._entity_id // empty')
FOUND_NAME=$(echo "$SEARCH_RESULT" | jq -r '.data[0].name // empty')

if [ -z "$PROJECT_ID" ]; then
  jq -n --arg name "$PROJECT_NAME" '{error: ("No project found matching " + $name)}'
  exit 0
fi

# 2. Get the project entity with relationships to find the folder
PROJECT_DATA=$(curl -sf "$BASE_URL/mem/_/$PROJECT_ID?view.rel_depth=1&view.format=json" 2>/dev/null)

if [ -z "$PROJECT_DATA" ]; then
  jq -n --arg id "$PROJECT_ID" '{error: ("Failed to get project entity " + $id)}'
  exit 0
fi

# Extract folder path from the project's includes relationships
WORKSPACE_PATH=$(echo "$PROJECT_DATA" | jq -r '
  [.data[0].includes.folder // []] | flatten |
  map(select(.path != null)) |
  .[0].path // empty
')

if [ -z "$WORKSPACE_PATH" ]; then
  # Try repository path as fallback
  WORKSPACE_PATH=$(echo "$PROJECT_DATA" | jq -r '
    [.data[0].includes.repository // []] | flatten |
    map(select(.path != null)) |
    .[0].path // empty
  ')
fi

if [ -z "$WORKSPACE_PATH" ]; then
  jq -n --arg name "$FOUND_NAME" --arg id "$PROJECT_ID" \
    '{error: ("Project " + $name + " (" + $id + ") has no linked workspace folder")}'
  exit 0
fi

# Verify the workspace exists on disk
if [ ! -d "$WORKSPACE_PATH" ]; then
  jq -n --arg path "$WORKSPACE_PATH" '{error: ("Workspace path does not exist: " + $path)}'
  exit 0
fi

# 3. Call the agent in that workspace
MODEL_FLAG=""
if [ -n "$MODEL" ]; then
  MODEL_FLAG="--model $MODEL"
fi

ANSWER=$(opencode run --dir "$WORKSPACE_PATH" $MODEL_FLAG "$QUESTION" 2>/dev/null)

if [ $? -ne 0 ] || [ -z "$ANSWER" ]; then
  echo '{"error": "Agent call failed or returned empty response"}'
  exit 0
fi

# 4. Return structured response
jq -n \
  --arg answer "$ANSWER" \
  --arg project_name "$FOUND_NAME" \
  --arg project_id "$PROJECT_ID" \
  --arg workspace_path "$WORKSPACE_PATH" \
  '{
    answer: $answer,
    project_name: $project_name,
    project_id: $project_id,
    workspace_path: $workspace_path
  }'
