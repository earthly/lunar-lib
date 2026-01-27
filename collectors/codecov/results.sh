#!/bin/bash
set -e

CMD="$LUNAR_CI_COMMAND"

# Check if this is an upload command
IS_UPLOAD=false
if echo "$CMD" | grep -qE '(^|\s)(upload|do-upload|upload-process)(\s|$)'; then
  IS_UPLOAD=true
elif echo "$CMD" | grep -qE '(\s|^)(-t(\s|=|[^[:space:]])|--token(\s|=))'; then
  IS_UPLOAD=true
elif echo "$CMD" | grep -qE '(\s|^)(-f(\s|=|[^[:space:]])|--file(\s|=))'; then
  IS_UPLOAD=true
fi

if [ "$IS_UPLOAD" != "true" ]; then
  exit 0
fi

# Determine which token to use
API_TOKEN=""
if [ "$LUNAR_VAR_USE_ENV_TOKEN" = "true" ] && [ -n "$CODECOV_TOKEN" ]; then
  API_TOKEN="$CODECOV_TOKEN"
fi
if [ -z "$API_TOKEN" ] && [ -n "$LUNAR_SECRET_CODECOV_API_TOKEN" ]; then
  API_TOKEN="$LUNAR_SECRET_CODECOV_API_TOKEN"
fi
if [ -z "$API_TOKEN" ]; then
  echo "Warning: No Codecov API token available, skipping results fetch" >&2
  exit 0
fi

# Parse component ID into service/owner/repo
# LUNAR_COMPONENT_ID format: github.com/owner/repo
COMPONENT_ID="$LUNAR_COMPONENT_ID"
SERVICE=$(echo "$COMPONENT_ID" | cut -d'/' -f1 | cut -d'.' -f1)
OWNER=$(echo "$COMPONENT_ID" | cut -d'/' -f2)
REPO=$(echo "$COMPONENT_ID" | cut -d'/' -f3)

if [ -z "$SERVICE" ] || [ -z "$OWNER" ] || [ -z "$REPO" ]; then
  echo "Error: Could not parse LUNAR_COMPONENT_ID: $COMPONENT_ID" >&2
  exit 1
fi

# Fetch coverage totals from Codecov API for this commit
SHA="$LUNAR_COMPONENT_GIT_SHA"
API_URL="https://api.codecov.io/api/v2/${SERVICE}/${OWNER}/repos/${REPO}/totals/"
if [ -n "$SHA" ]; then
  API_URL="${API_URL}?sha=${SHA}"
fi
RESULTS=$(curl -fsS --connect-timeout 10 --max-time 30 \
  -H "Authorization: Bearer $API_TOKEN" \
  "$API_URL" 2>/dev/null || echo "")

if [ -n "$RESULTS" ]; then
  # Extract coverage from totals response (per Codecov API docs)
  COVERAGE=$(echo "$RESULTS" | jq -r '.totals.coverage // empty')
  if [ -n "$COVERAGE" ]; then
    # Write coverage percentage - presence signals upload succeeded
    lunar collect -j ".testing.coverage.percentage" "$COVERAGE"
    # Write full API response to native field for policies needing raw data
    echo "$RESULTS" | lunar collect -j ".testing.coverage.native.codecov" -
  fi
fi
