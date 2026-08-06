#!/bin/bash

set -e

# helpers.sh sits alongside this script in the collector dir at runtime.
# shellcheck disable=SC1091
source "$(dirname "$0")/helpers.sh"

# After-json variant of ticket.sh. Reads the PR/MR title from .vcs.pr.title in
# Component JSON (populated by the github/gitlab collector) instead of calling
# the GitHub API, so it needs no GH_TOKEN and works on any VCS provider.
# Transitional: folds into the `ticket` collector once after-json is stable.

COMPONENT_JSON=$(lunar component get-json "$LUNAR_COMPONENT_ID" 2>/dev/null || echo "")
PR_TITLE=$(echo "$COMPONENT_JSON" | jq -r '.vcs.pr.title // empty' 2>/dev/null)

if [ -z "$PR_TITLE" ]; then
  echo "No .vcs.pr.title in Component JSON (PR-metadata collector not run yet?), skipping." >&2
  exit 0
fi

# Extract ticket ID from the title (shared logic with the code-hook collector).
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

# Validate required Jira API configuration (degrade gracefully otherwise).
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

# Fetch ticket from Jira REST API using classic API token + HTTP Basic auth.
JIRA_API_URL="${JIRA_BASE_URL%/}/rest/api/3/issue/${TICKET_KEY}"
set +e
JIRA_RESPONSE="$(curl -fsS \
  -u "${JIRA_USER}:${LUNAR_SECRET_JIRA_TOKEN}" \
  -H 'Accept: application/json' \
  "$JIRA_API_URL")"
CURL_STATUS=$?
set -e

if [ $CURL_STATUS -ne 0 ] || [ -z "$JIRA_RESPONSE" ]; then
  # Exit 0, not 1: a non-zero exit makes the Hub discard every value this run
  # collected, erasing the ticket reference written above.
  echo "Unable to fetch Jira issue ${TICKET_KEY} from ${JIRA_API_URL}." >&2
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

echo "$JIRA_RESPONSE" | lunar collect -j ".vcs.pr.ticket.native.jira" -
