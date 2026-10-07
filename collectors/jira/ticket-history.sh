#!/bin/bash

# LUNAR_COMPONENT_ID / LUNAR_COMPONENT_PR are injected by the Lunar runtime —
# they are not local assignments or typos of each other.
# shellcheck disable=SC2153
set -e

# helpers.sh sits alongside this script in the collector dir at runtime.
# shellcheck disable=SC1091
source "$(dirname "$0")/helpers.sh"

# Only run in PR context.
if [ -z "${LUNAR_COMPONENT_PR:-}" ]; then
  echo "Not in a PR context, skipping." >&2
  exit 0
fi

# Require GH_TOKEN to fetch PR metadata.
if [ -z "${LUNAR_SECRET_GH_TOKEN:-}" ]; then
  echo "ticket-history requires GH_TOKEN secret to query GitHub." >&2
  exit 1
fi

resolve_ticket_path || exit 1

# Fetch PR title and description from GitHub.
fetch_pr_metadata || exit 1

# Resolve the ticket the same way the ticket sub-collector does, validating
# candidates against Jira. Resolving independently but unvalidated would count
# reuse for a different key than the one ticket collected whenever the first
# candidate turns out not to exist.
RESOLVE_STATUS=0
resolve_ticket || RESOLVE_STATUS=$?

case $RESOLVE_STATUS in
  1)
    echo "PR references no ticket." >&2
    exit 0
    ;;
  2)
    echo "Jira rejected the credentials for ${LUNAR_VAR_JIRA_USER}." >&2
    exit 1
    ;;
esac

# Get database connection string.
CONN_STRING=$(lunar sql connection-string 2>/dev/null) || true

if [ -z "$CONN_STRING" ]; then
  echo "lunar sql connection-string not available, skipping ticket-history." >&2
  exit 0
fi

# Verify psql is available. The SQL API is reachable (connection string above),
# so a missing client is a broken runtime image, not an unsupported environment.
if ! command -v psql &> /dev/null; then
  echo "psql not found, cannot query ticket reuse." >&2
  exit 1
fi

# Sanitize inputs for SQL.
SAFE_TICKET_KEY=$(echo "$TICKET_KEY" | sed "s/'/''/g")
SAFE_COMPONENT_ID=$(echo "$LUNAR_COMPONENT_ID" | sed "s/'/''/g")
SAFE_PR=$(echo "$LUNAR_COMPONENT_PR" | sed "s/'/''/g")

# The id recorded at TICKET_PATH, e.g. component_json->'vcs'->'pr'->'ticket'->>'id'.
# resolve_ticket_path admits only letters, digits and underscores per segment.
ID_EXPR="component_json"
IFS='.' read -ra SEGMENTS <<< "${TICKET_PATH#.}"
for SEGMENT in "${SEGMENTS[@]}"; do
  ID_EXPR+="->'${SEGMENT}'"
done
ID_EXPR+="->>'id'"

# Query for other PRs using the same ticket.
QUERY="
  SELECT COUNT(DISTINCT (component_id, pr))
  FROM components_latest
  WHERE pr IS NOT NULL
    AND ${ID_EXPR} = '${SAFE_TICKET_KEY}'
    AND NOT (component_id = '${SAFE_COMPONENT_ID}' AND pr::text = '${SAFE_PR}')
"

REUSE_COUNT=$(psql "$CONN_STRING" -t -A -c "$QUERY" 2>&1) || true

# Validate result is a number.
if ! [[ "$REUSE_COUNT" =~ ^[0-9]+$ ]]; then
  echo "Failed to query ticket reuse count: ${REUSE_COUNT}" >&2
  exit 1
fi

lunar collect -j "${TICKET_PATH}.reuse_count" "$REUSE_COUNT"
