#!/bin/bash
# Run tests only for changed apps/connectors
# 
# If you edit an app/connector, it MUST have tests or the commit fails.
# This progressively enforces test coverage as code is touched.
#
# Usage: ./scripts/test-changed.sh [--all] [--staged]

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

# Always run structure tests (fast, validates layout)
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
  echo "✅ No files changed"
  exit 0
fi

# Extract unique apps from changed files (apps/{app}/...)
AFFECTED_APPS=$(echo "$CHANGED_FILES" | grep -oE '^apps/[^/]+' | sort -u | cut -d/ -f2 || true)

# Extract unique connectors from changed files (apps/{app}/connectors/{connector}/...)
AFFECTED_CONNECTORS=$(echo "$CHANGED_FILES" | grep -oE '^apps/[^/]+/connectors/[^/]+' | sort -u || true)

if [ -z "$AFFECTED_APPS" ] && [ -z "$AFFECTED_CONNECTORS" ]; then
  echo "✅ No app/connector files changed"
  exit 0
fi

echo ""
echo "📦 Changed apps: ${AFFECTED_APPS:-none}"
echo "🔌 Changed connectors: ${AFFECTED_CONNECTORS:-none}"
echo ""

MISSING_TESTS=()

# Check and run tests for each affected app
for app in $AFFECTED_APPS; do
  APP_TEST_DIR="apps/$app/tests"
  
  if [ ! -d "$APP_TEST_DIR" ]; then
    MISSING_TESTS+=("apps/$app")
  else
    # Check there's at least one test file
    TEST_COUNT=$(find "$APP_TEST_DIR" -name "*.test.ts" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$TEST_COUNT" -eq 0 ]; then
      MISSING_TESTS+=("apps/$app")
    else
      echo "🧪 Testing apps/$app..."
      npm test -- "$APP_TEST_DIR" --run || exit 1
    fi
  fi
done

# Check and run tests for each affected connector
for connector_path in $AFFECTED_CONNECTORS; do
  CONNECTOR_TEST_DIR="$connector_path/tests"
  
  if [ ! -d "$CONNECTOR_TEST_DIR" ]; then
    MISSING_TESTS+=("$connector_path")
  else
    # Check there's at least one test file
    TEST_COUNT=$(find "$CONNECTOR_TEST_DIR" -name "*.test.ts" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$TEST_COUNT" -eq 0 ]; then
      MISSING_TESTS+=("$connector_path")
    else
      echo "🧪 Testing $connector_path..."
      npm test -- "$CONNECTOR_TEST_DIR" --run || exit 1
    fi
  fi
done

# If any changed apps/connectors are missing tests, fail
if [ ${#MISSING_TESTS[@]} -gt 0 ]; then
  echo ""
  echo "❌ COMMIT BLOCKED: Missing tests for changed code"
  echo ""
  echo "The following need tests before you can commit:"
  for missing in "${MISSING_TESTS[@]}"; do
    echo "  - $missing/tests/*.test.ts"
  done
  echo ""
  echo "Add at least one test file, then try again."
  exit 1
fi

echo ""
echo "✅ All tests passed"
