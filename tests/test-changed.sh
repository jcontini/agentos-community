#!/bin/bash
# Run validation + MCP smoke checks for changed skills
# Called by pre-push hook or manually
#
# Usage: ./scripts/test-changed.sh [--all] [--staged] [--committed]

set -e

cd "$(dirname "$0")/../.."

# Parse args
RUN_ALL=false
CHECK_MODE="committed"  # Default: check commits not yet pushed

for arg in "$@"; do
  case $arg in
    --all) RUN_ALL=true ;;
    --staged) CHECK_MODE="staged" ;;
    --committed) CHECK_MODE="committed" ;;
  esac
done

if [ "$RUN_ALL" = true ]; then
  echo "🔄 Running full validation..."
  npm run validate
  exit 0
fi

# Get changed files based on mode
if [ "$CHECK_MODE" = "staged" ]; then
  CHANGED_FILES=$(git diff --cached --name-only --diff-filter=ACMR 2>/dev/null || echo "")
else
  # Files changed in commits not yet pushed
  CHANGED_FILES=$(git diff @{u}..HEAD --name-only --diff-filter=ACMR 2>/dev/null || \
                  git diff HEAD~5..HEAD --name-only --diff-filter=ACMR 2>/dev/null || echo "")
fi

if [ -z "$CHANGED_FILES" ]; then
  echo "✅ No files changed"
  exit 0
fi

# Extract unique skills from changed files (skills/{skill}/...)
AFFECTED_SKILLS=$(echo "$CHANGED_FILES" | grep -oE '^skills/[^/]+' | sort -u | cut -d/ -f2 || true)

if [ -z "$AFFECTED_SKILLS" ]; then
  echo "✅ No skill files changed"
  exit 0
fi

echo "📦 Checking skills: $AFFECTED_SKILLS"
echo ""

# First, run structural validation
echo "📋 Validation..."
node tests/skills/scripts/validate.mjs $AFFECTED_SKILLS || exit 1
echo ""

echo "🔌 MCP smoke test..."
npm run mcp:test -- $AFFECTED_SKILLS || exit 1

echo ""
echo "✅ Done: validated + MCP smoke tested"
