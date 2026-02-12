#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

echo "DEBUG: ticket-history starting" >&2
echo "DEBUG: LUNAR_COMPONENT_PR='${LUNAR_COMPONENT_PR:-}'" >&2

# Only run in PR context.
if [ -z "${LUNAR_COMPONENT_PR:-}" ]; then
  echo "Not in a PR context, skipping." >&2
  exit 0
fi

# Require GH_TOKEN to fetch PR title.
if [ -z "${LUNAR_SECRET_GH_TOKEN:-}" ]; then
  echo "DEBUG: GH_TOKEN not set, skipping." >&2
  exit 0
fi

# Fetch PR title from GitHub.
echo "DEBUG: fetching PR title..." >&2
PR_TITLE="$(fetch_pr_title)" || exit 0
echo "DEBUG: PR_TITLE='$PR_TITLE'" >&2

# Extract ticket ID from PR title.
TICKET_KEY="$(extract_ticket_id "$PR_TITLE")" || exit 0
echo "DEBUG: TICKET_KEY='$TICKET_KEY'" >&2

if [ -z "$TICKET_KEY" ]; then
  echo "DEBUG: no ticket key found, exiting." >&2
  exit 0
fi

# Get database connection string.
echo "DEBUG: getting connection string..." >&2
CONN_STRING=$(lunar sql connection-string 2>/dev/null) || true
echo "DEBUG: CONN_STRING='${CONN_STRING:0:80}'" >&2

if [ -z "$CONN_STRING" ] || [[ "$CONN_STRING" == *"Error"* ]]; then
  # Fall back to secrets if lunar sql connection-string isn't available.
  if [ -n "${LUNAR_SECRET_PG_PASSWORD:-}" ] && [ -n "${LUNAR_HUB_HOST:-}" ]; then
    PG_USER="${LUNAR_SECRET_PG_USER:-api3}"
    CONN_STRING="postgres://${PG_USER}:${LUNAR_SECRET_PG_PASSWORD}@${LUNAR_HUB_HOST}:5432/hub?sslmode=disable"
    echo "DEBUG: using fallback CONN_STRING from secrets" >&2
  else
    echo "DEBUG: no connection string and no fallback secrets, skipping." >&2
    exit 0
  fi
fi

# Verify psql is available.
if ! command -v psql &> /dev/null; then
  echo "DEBUG: psql not found, skipping." >&2
  exit 0
fi
echo "DEBUG: psql at $(which psql)" >&2

# Sanitize inputs for SQL.
SAFE_TICKET_KEY=$(echo "$TICKET_KEY" | sed "s/'/''/g")
SAFE_COMPONENT_ID=$(echo "$LUNAR_COMPONENT_ID" | sed "s/'/''/g")
SAFE_PR=$(echo "$LUNAR_COMPONENT_PR" | sed "s/'/''/g")

# Query for other PRs using the same ticket.
QUERY="
  SELECT COUNT(DISTINCT (component_id, pr))
  FROM components_latest2
  WHERE pr IS NOT NULL
    AND component_json->'vcs'->'pr'->'ticket'->>'id' = '${SAFE_TICKET_KEY}'
    AND NOT (component_id = '${SAFE_COMPONENT_ID}' AND pr::text = '${SAFE_PR}')
"

echo "DEBUG: running psql query..." >&2
REUSE_COUNT=$(psql "$CONN_STRING" -t -A -c "$QUERY" 2>&1) || true
echo "DEBUG: REUSE_COUNT='${REUSE_COUNT:0:200}'" >&2

# Validate result is a number.
if ! [[ "$REUSE_COUNT" =~ ^[0-9]+$ ]]; then
  echo "DEBUG: non-numeric result, skipping." >&2
  exit 0
fi

echo "DEBUG: writing ticket_reuse_count=$REUSE_COUNT" >&2
lunar collect -j ".jira.ticket_reuse_count" "$REUSE_COUNT"
