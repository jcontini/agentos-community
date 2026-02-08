#!/bin/bash
# Run full integration tests for changed apps
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
  echo "🔄 Running all tests..."
  npm test -- --run
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

# Extract unique adapters from changed files (adapters/{adapter}/...)
AFFECTED_APPS=$(echo "$CHANGED_FILES" | grep -oE '^adapters/[^/]+' | sort -u | cut -d/ -f2 || true)

if [ -z "$AFFECTED_APPS" ]; then
  echo "✅ No adapter files changed"
  exit 0
fi

echo "📦 Testing adapters: $AFFECTED_APPS"
echo ""

# First, run schema validation
echo "📋 Schema validation..."
node tests/adapters/scripts/validate.mjs $AFFECTED_APPS || exit 1
echo ""

TESTED=0
SKIPPED=0

# Run tests for each affected adapter that has tests
for app in $AFFECTED_APPS; do
  APP_TEST_DIR="adapters/$app/tests"
  
  if [ -d "$APP_TEST_DIR" ]; then
    TEST_COUNT=$(find "$APP_TEST_DIR" -name "*.test.ts" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$TEST_COUNT" -gt 0 ]; then
      echo "🧪 Testing adapters/$app..."
      npm test -- "$APP_TEST_DIR" --run || exit 1
      TESTED=$((TESTED + 1))
    else
      echo "⏭️  adapters/$app: no test files"
      SKIPPED=$((SKIPPED + 1))
    fi
  else
    echo "⏭️  adapters/$app: no tests/ directory"
    SKIPPED=$((SKIPPED + 1))
  fi
done

echo ""
echo "✅ Done: $TESTED tested, $SKIPPED skipped"
