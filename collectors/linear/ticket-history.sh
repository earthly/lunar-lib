#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Only run in PR context.
if [ -z "${LUNAR_COMPONENT_PR:-}" ]; then
  echo "Not in a PR context, skipping." >&2
  exit 0
fi

# With github_app set, mint a token from that Hub GitHub App (`lunar github-app add`)
# instead of using the GH_TOKEN secret. The token asks for only the permissions this
# script uses, so an App without them falls back; github_app_only turns that off.
if [ -n "${LUNAR_VAR_GITHUB_APP:-}" ] && APP_TOKEN=$(lunar github-app get-token "$LUNAR_VAR_GITHUB_APP" --permission pull_requests=read) \
    && [ -n "$APP_TOKEN" ]; then
  echo "GitHub auth: GitHub App $LUNAR_VAR_GITHUB_APP" >&2
  export LUNAR_SECRET_GH_TOKEN="$APP_TOKEN"
elif [ "${LUNAR_VAR_GITHUB_APP_ONLY:-false}" = "true" ]; then
  echo "GitHub auth: no token from GitHub App ${LUNAR_VAR_GITHUB_APP:-(github_app is not set)}, and github_app_only is set" >&2
  exit 1
elif [ -n "${LUNAR_VAR_GITHUB_APP:-}" ]; then
  echo "GitHub auth: GH_TOKEN secret, because GitHub App $LUNAR_VAR_GITHUB_APP minted no token" >&2
fi

# Require GH_TOKEN to fetch PR title.
if [ -z "${LUNAR_SECRET_GH_TOKEN:-}" ]; then
  echo "ticket-history requires GH_TOKEN secret to query GitHub." >&2
  exit 0
fi

# Fetch PR title from GitHub.
PR_TITLE="$(fetch_pr_title)" || exit 0

# Extract ticket ID from PR title.
TICKET_KEY="$(extract_ticket_id "$PR_TITLE")" || exit 0

if [ -z "$TICKET_KEY" ]; then
  exit 0
fi

# Get database connection string.
CONN_STRING=$(lunar sql connection-string 2>/dev/null) || true

if [ -z "$CONN_STRING" ]; then
  echo "lunar sql connection-string not available, skipping ticket-history." >&2
  exit 0
fi

# Verify psql is available.
if ! command -v psql &> /dev/null; then
  echo "psql not found, skipping ticket-history." >&2
  exit 0
fi

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

REUSE_COUNT=$(PGCONNECT_TIMEOUT=10 PGOPTIONS='-c statement_timeout=30000' \
  psql "$CONN_STRING" -t -A -c "$QUERY" 2>&1) || true

# Validate result is a number.
if ! [[ "$REUSE_COUNT" =~ ^[0-9]+$ ]]; then
  echo "Failed to query ticket reuse count, skipping." >&2
  exit 0
fi

lunar collect -j ".vcs.pr.ticket.reuse_count" "$REUSE_COUNT"
