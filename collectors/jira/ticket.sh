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
  echo "Jira collector requires GH_TOKEN secret to query GitHub." >&2
  exit 0
fi

# Fetch PR title from GitHub.
PR_TITLE="$(fetch_pr_title)" || exit 0

# Extract ticket ID from PR title.
TICKET_KEY="$(extract_ticket_id "$PR_TITLE")" || exit 0

if [ -z "$TICKET_KEY" ]; then
  exit 0
fi

# Write the ticket ID and source regardless of Jira API result.
JIRA_BASE_URL="${LUNAR_VAR_JIRA_BASE_URL:-}"
TICKET_URL=""
if [ -n "$JIRA_BASE_URL" ]; then
  TICKET_URL="${JIRA_BASE_URL%/}/browse/${TICKET_KEY}"
fi

lunar collect ".vcs.pr.ticket.id" "$TICKET_KEY"
jq -n '{"tool": "jira", "integration": "api"}' | lunar collect -j ".vcs.pr.ticket.source" -

if [ -n "$TICKET_URL" ]; then
  lunar collect ".vcs.pr.ticket.url" "$TICKET_URL"
fi

# Validate required Jira API configuration.
if [ -z "$JIRA_BASE_URL" ]; then
  echo "jira_base_url input not set, skipping Jira API validation." >&2
  exit 0
fi

JIRA_USER="${LUNAR_VAR_JIRA_USER:-}"
if [ -z "$JIRA_USER" ]; then
  echo "jira_user input not set, skipping Jira API validation." >&2
  exit 0
fi

if [ -z "${LUNAR_SECRET_JIRA_TOKEN:-}" ]; then
  echo "JIRA_TOKEN secret not set, skipping Jira API validation." >&2
  exit 0
fi

# Fetch ticket from Jira REST API.
JIRA_API_URL="${JIRA_BASE_URL%/}/rest/api/3/issue/${TICKET_KEY}"

set +e
JIRA_RESPONSE="$(curl -fsS \
  -u "${JIRA_USER}:${LUNAR_SECRET_JIRA_TOKEN}" \
  -H 'Accept: application/json' \
  "$JIRA_API_URL")"
CURL_STATUS=$?
set -e

if [ $CURL_STATUS -ne 0 ] || [ -z "$JIRA_RESPONSE" ]; then
  echo "Unable to fetch Jira issue ${TICKET_KEY} from ${JIRA_BASE_URL}." >&2
  exit 0
fi

# Ticket exists — write normalized fields to generic paths.
lunar collect -j ".vcs.pr.ticket.valid" true

TICKET_STATUS="$(echo "$JIRA_RESPONSE" | jq -r '.fields.status.name // empty')"
TICKET_TYPE="$(echo "$JIRA_RESPONSE" | jq -r '.fields.issuetype.name // empty')"
TICKET_SUMMARY="$(echo "$JIRA_RESPONSE" | jq -r '.fields.summary // empty')"
TICKET_ASSIGNEE="$(echo "$JIRA_RESPONSE" | jq -r '.fields.assignee.emailAddress // empty')"

lunar collect \
  ".vcs.pr.ticket.status" "$TICKET_STATUS" \
  ".vcs.pr.ticket.type" "$TICKET_TYPE" \
  ".vcs.pr.ticket.summary" "$TICKET_SUMMARY" \
  ".vcs.pr.ticket.assignee" "$TICKET_ASSIGNEE"

# Write full raw response under native.jira.
echo "$JIRA_RESPONSE" | lunar collect -j ".vcs.pr.ticket.native.jira" -
