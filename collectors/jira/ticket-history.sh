#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

echo "DEBUG ticket-history: starting" >&2
echo "DEBUG ticket-history: LUNAR_COMPONENT_PR='${LUNAR_COMPONENT_PR:-}'" >&2

# Only run in PR context.
if [ -z "${LUNAR_COMPONENT_PR:-}" ]; then
  echo "Not in a PR context, skipping." >&2
  exit 0
fi

# Require GH_TOKEN to fetch PR title.
if [ -z "${LUNAR_SECRET_GH_TOKEN:-}" ]; then
  echo "ticket-history requires GH_TOKEN secret to query GitHub." >&2
  exit 0
fi

# Fetch PR title from GitHub.
PR_TITLE="$(fetch_pr_title)" || exit 0
echo "DEBUG ticket-history: PR_TITLE='$PR_TITLE'" >&2

# Extract ticket ID from PR title.
TICKET_KEY="$(extract_ticket_id "$PR_TITLE")" || exit 0
echo "DEBUG ticket-history: TICKET_KEY='$TICKET_KEY'" >&2

if [ -z "$TICKET_KEY" ]; then
  echo "DEBUG ticket-history: TICKET_KEY empty, exiting" >&2
  exit 0
fi

# Temporarily write 0 to verify the basic flow works, then attempt SQL.
echo "DEBUG ticket-history: writing default ticket_reuse_count=0" >&2
lunar collect -j ".jira.ticket_reuse_count" "0"

# Now try the SQL query to get the actual count.
CONN_STRING=$(lunar sql connection-string 2>/dev/null) || true
echo "DEBUG ticket-history: CONN_STRING='${CONN_STRING:0:80}'" >&2

if [ -z "$CONN_STRING" ]; then
  echo "DEBUG ticket-history: connection string empty, using default 0" >&2
  exit 0
fi

if ! command -v psql &> /dev/null; then
  echo "DEBUG ticket-history: psql not found, using default 0" >&2
  exit 0
fi

# Sanitize inputs for SQL.
SAFE_TICKET_KEY=$(echo "$TICKET_KEY" | sed "s/'/''/g")
SAFE_COMPONENT_ID=$(echo "$LUNAR_COMPONENT_ID" | sed "s/'/''/g")
SAFE_PR=$(echo "$LUNAR_COMPONENT_PR" | sed "s/'/''/g")

QUERY="
  SELECT COUNT(DISTINCT (component_id, pr))
  FROM components_latest
  WHERE pr IS NOT NULL
    AND component_json->'vcs'->'pr'->'ticket'->>'id' = '${SAFE_TICKET_KEY}'
    AND NOT (component_id = '${SAFE_COMPONENT_ID}' AND pr::text = '${SAFE_PR}')
"

REUSE_COUNT=$(psql "$CONN_STRING" -t -A -c "$QUERY" 2>&1) || true
echo "DEBUG ticket-history: REUSE_COUNT='${REUSE_COUNT:0:200}'" >&2

if [[ "$REUSE_COUNT" =~ ^[0-9]+$ ]]; then
  echo "DEBUG ticket-history: SQL succeeded, writing actual count=$REUSE_COUNT" >&2
  lunar collect -j ".jira.ticket_reuse_count" "$REUSE_COUNT"
else
  echo "DEBUG ticket-history: SQL failed (result: '${REUSE_COUNT:0:200}'), keeping default 0" >&2
fi
