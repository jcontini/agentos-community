#!/bin/bash
# Run tests only for changed apps/connectors
# Usage: ./scripts/test-changed.sh [--all] [--staged]
#   --all     Run all tests (for CI)
#   --staged  Check only staged files (default for pre-commit)

set -e

cd "$(dirname "$0")/.."

# Parse args
RUN_ALL=false
CHECK_STAGED=true

for arg in "$@"; do
  case $arg in
    --all) RUN_ALL=true ;;
    --staged) CHECK_STAGED=true ;;
    --committed) CHECK_STAGED=false ;;
  esac
done

# Always run structure tests (fast, validates overall layout)
echo "📋 Running structure tests..."
npm test -- tests/structure.test.ts --run

if [ "$RUN_ALL" = true ]; then
  echo "🔄 Running all tests..."
  npm test -- --run
  exit 0
fi

# Get changed files
if [ "$CHECK_STAGED" = true ]; then
  CHANGED_FILES=$(git diff --cached --name-only --diff-filter=ACMR 2>/dev/null || echo "")
else
  CHANGED_FILES=$(git diff HEAD~1 --name-only --diff-filter=ACMR 2>/dev/null || echo "")
fi

if [ -z "$CHANGED_FILES" ]; then
  echo "✅ No files changed, skipping app tests"
  exit 0
fi

# Extract unique apps and connectors from changed files
# Pattern: apps/{app}/... or apps/{app}/connectors/{connector}/...
AFFECTED_APPS=$(echo "$CHANGED_FILES" | grep -oE '^apps/[^/]+' | sort -u | cut -d/ -f2 || true)
AFFECTED_CONNECTORS=$(echo "$CHANGED_FILES" | grep -oE '^apps/[^/]+/connectors/[^/]+' | sort -u || true)

if [ -z "$AFFECTED_APPS" ] && [ -z "$AFFECTED_CONNECTORS" ]; then
  echo "✅ No app/connector files changed"
  exit 0
fi

echo ""
echo "📦 Changed apps: ${AFFECTED_APPS:-none}"
echo "🔌 Changed connectors: ${AFFECTED_CONNECTORS:-none}"
echo ""

# Run tests for each affected app that has tests
for app in $AFFECTED_APPS; do
  APP_TEST_DIR="apps/$app/tests"
  if [ -d "$APP_TEST_DIR" ]; then
    echo "🧪 Testing $app..."
    npm test -- "$APP_TEST_DIR" --run || exit 1
  fi
done

# Run tests for each affected connector that has tests
for connector_path in $AFFECTED_CONNECTORS; do
  CONNECTOR_TEST_DIR="$connector_path/tests"
  if [ -d "$CONNECTOR_TEST_DIR" ]; then
    echo "🧪 Testing $connector_path..."
    npm test -- "$CONNECTOR_TEST_DIR" --run || exit 1
  fi
done

echo ""
echo "✅ All affected tests passed"
