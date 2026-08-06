#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Only run in PR context.
if [ -z "${LUNAR_COMPONENT_PR:-}" ]; then
  echo "Not in a PR context, skipping." >&2
  exit 0
fi

# Require GH_TOKEN to fetch PR metadata.
if [ -z "${LUNAR_SECRET_GH_TOKEN:-}" ]; then
  echo "Jira collector requires GH_TOKEN secret to query GitHub." >&2
  exit 1
fi

# Fetch PR title and description from GitHub.
fetch_pr_metadata || exit 1

# Resolve the ticket, validating candidates against Jira in order.
RESOLVE_STATUS=0
resolve_ticket || RESOLVE_STATUS=$?

case $RESOLVE_STATUS in
  1)
    echo "PR references no ticket." >&2
    exit 0
    ;;
  2)
    # Exit 1: rejected credentials are a misconfiguration an operator has to
    # fix, not a property of this PR, so the run itself has to show as failed.
    echo "Jira rejected the credentials for ${LUNAR_VAR_JIRA_USER}." >&2
    exit 1
    ;;
esac

# Write the ticket reference. This happens even when Jira could not confirm the
# ticket, so an outage does not make the PR look ticket-less.
lunar collect ".vcs.pr.ticket.id" "$TICKET_KEY"
jq -n '{"tool": "jira", "integration": "api"}' | lunar collect -j ".vcs.pr.ticket.source" -

JIRA_BASE_URL="${LUNAR_VAR_JIRA_BASE_URL:-}"
if [ -n "$JIRA_BASE_URL" ]; then
  lunar collect ".vcs.pr.ticket.url" "${JIRA_BASE_URL%/}/browse/${TICKET_KEY}"
fi

if [ -z "$TICKET_VALID" ]; then
  # Exit 0, not 1: a non-zero exit makes the Hub discard every value this run
  # collected, which would erase the ticket reference written above and
  # misreport the PR as ticket-less. tracker_error tells the ticket-valid
  # policy why .valid is missing, so it can name the real cause; leaving it
  # unset means validation was never configured.
  if [ -n "$TICKET_ERROR" ]; then
    lunar collect ".vcs.pr.ticket.tracker_error" "$TICKET_ERROR"
  else
    echo "Jira API validation not configured, skipping." >&2
  fi
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
