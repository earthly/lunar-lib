#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Only run in PR context.
if [ -z "${LUNAR_COMPONENT_PR:-}" ]; then
  echo "Not in a PR context, skipping." >&2
  exit 0
fi

# Require GH_TOKEN to fetch PR title.
if [ -z "${LUNAR_SECRET_GH_TOKEN:-}" ]; then
  echo "Linear collector requires GH_TOKEN secret to query GitHub." >&2
  exit 0
fi

# Fetch PR title from GitHub.
PR_TITLE="$(fetch_pr_title)" || exit 0

# Extract ticket ID from PR title.
TICKET_KEY="$(extract_ticket_id "$PR_TITLE")" || exit 0

if [ -z "$TICKET_KEY" ]; then
  exit 0
fi

# Write the ticket ID and source regardless of Linear API result.
lunar collect ".vcs.pr.ticket.id" "$TICKET_KEY"
jq -n '{"tool": "linear", "integration": "api"}' | lunar collect -j ".vcs.pr.ticket.source" -

# Validate required Linear API configuration.
if [ -z "${LUNAR_SECRET_LINEAR_API_KEY:-}" ]; then
  echo "LINEAR_API_KEY secret not set, skipping Linear API validation." >&2
  exit 0
fi

# Split ticket key into team key and number (e.g. ENG-417 -> ENG + 417).
TEAM_KEY="${TICKET_KEY%-*}"
ISSUE_NUM="${TICKET_KEY##*-}"

if [ -z "$TEAM_KEY" ] || [ -z "$ISSUE_NUM" ]; then
  echo "Could not parse team key and number from ${TICKET_KEY}." >&2
  exit 0
fi

# Build GraphQL query — filter by team key + issue number.
QUERY='query($num: Float!, $teamKey: String!) { issues(filter: { number: { eq: $num }, team: { key: { eq: $teamKey } } }, first: 1) { nodes { id identifier title url state { name type } assignee { email displayName } labels { nodes { name } } priority priorityLabel team { key name } } } }'

PAYLOAD=$(jq -n --arg q "$QUERY" --argjson num "$ISSUE_NUM" --arg tk "$TEAM_KEY" \
  '{"query": $q, "variables": {"num": $num, "teamKey": $tk}}')

set +e
RESPONSE=$(curl -fsS -X POST https://api.linear.app/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: ${LUNAR_SECRET_LINEAR_API_KEY}" \
  -d "$PAYLOAD")
CURL_STATUS=$?
set -e

if [ $CURL_STATUS -ne 0 ] || [ -z "$RESPONSE" ]; then
  echo "Unable to query Linear API for ticket ${TICKET_KEY}." >&2
  exit 0
fi

# Check for GraphQL errors.
GQL_ERROR=$(echo "$RESPONSE" | jq -r '.errors[0].message // empty')
if [ -n "$GQL_ERROR" ]; then
  echo "Linear API error: ${GQL_ERROR}" >&2
  exit 0
fi

# Check if we got a result.
NODE=$(echo "$RESPONSE" | jq '.data.issues.nodes[0] // empty')
if [ -z "$NODE" ] || [ "$NODE" = "null" ] || [ "$NODE" = "" ]; then
  echo "Ticket ${TICKET_KEY} not found in Linear." >&2
  exit 0
fi

# Ticket exists — write normalized fields.
lunar collect -j ".vcs.pr.ticket.valid" true

TICKET_URL=$(echo "$NODE" | jq -r '.url // empty')
TICKET_STATUS=$(echo "$NODE" | jq -r '.state.name // empty')
TICKET_SUMMARY=$(echo "$NODE" | jq -r '.title // empty')
TICKET_ASSIGNEE=$(echo "$NODE" | jq -r '.assignee.email // empty')

[ -n "$TICKET_URL" ] && lunar collect ".vcs.pr.ticket.url" "$TICKET_URL"

lunar collect \
  ".vcs.pr.ticket.status" "$TICKET_STATUS" \
  ".vcs.pr.ticket.summary" "$TICKET_SUMMARY" \
  ".vcs.pr.ticket.assignee" "$TICKET_ASSIGNEE"

# Extract type from labels if configured.
TYPE_LABELS="${LUNAR_VAR_TYPE_LABELS:-}"
if [ -n "$TYPE_LABELS" ]; then
  ISSUE_LABELS=$(echo "$NODE" | jq -r '.labels.nodes[].name' 2>/dev/null)

  IFS=',' read -ra TYPES <<< "$TYPE_LABELS"
  for t in "${TYPES[@]}"; do
    t=$(echo "$t" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    if echo "$ISSUE_LABELS" | grep -qix "$t"; then
      lunar collect ".vcs.pr.ticket.type" "$t"
      break
    fi
  done
fi

# Write full raw response under native.linear.
echo "$NODE" | lunar collect -j ".vcs.pr.ticket.native.linear" -
