#!/bin/bash

# LUNAR_COMPONENT_ID / LUNAR_COMPONENT_PR are injected by the Lunar runtime —
# they are not local assignments or typos of each other.
# shellcheck disable=SC2153
set -e

# helpers.sh sits alongside this script in the collector dir at runtime.
# shellcheck disable=SC1091
source "$(dirname "$0")/helpers.sh"

# After-json variant of ticket.sh. Instead of fetching PR metadata from the
# GitHub API, it reads the PR/MR title and description from .vcs.pr in Component
# JSON (populated by the github/gitlab collector), then resolves and validates
# the ticket with the same shared logic. Needs no GH_TOKEN and works on any VCS
# provider. Transitional: folds into `ticket` once after-json is stable.

# In PR context the runtime sets LUNAR_COMPONENT_PR. Pass it through so
# get-json returns the PR-scoped Component JSON (which carries .vcs.pr.*)
# rather than the main-branch JSON. `lunar component get-json` does not default
# --pr from the environment (unlike the component id, which falls back to
# LUNAR_COMPONENT_ID), so without this the PR title is never seen and the
# collector skips. Empty array when unset → no --pr, same as before.
pr_arg=()
[ -n "${LUNAR_COMPONENT_PR:-}" ] && pr_arg=(--pr "$LUNAR_COMPONENT_PR")

COMPONENT_JSON=$(lunar component get-json "$LUNAR_COMPONENT_ID" "${pr_arg[@]}" 2>/dev/null || echo "")
PR_TITLE=$(echo "$COMPONENT_JSON" | jq -r '.vcs.pr.title // empty' 2>/dev/null)
# PR_BODY is consumed by resolve_ticket/list_ticket_candidates in helpers.sh.
# shellcheck disable=SC2034
PR_BODY=$(echo "$COMPONENT_JSON" | jq -r '.vcs.pr.description // empty' 2>/dev/null)

if [ -z "$PR_TITLE" ]; then
  echo "No .vcs.pr.title in Component JSON (PR-metadata collector not run yet?), skipping." >&2
  exit 0
fi

# Resolve the ticket the same way the `ticket` sub-collector does — from the
# title and description — validating candidates against Jira in order.
RESOLVE_STATUS=0
resolve_ticket || RESOLVE_STATUS=$?

case $RESOLVE_STATUS in
  1)
    echo "PR references no ticket." >&2
    exit 0
    ;;
  2)
    # Exit 1: rejected credentials are an operator misconfiguration, not a
    # property of this PR, so the run itself has to show as failed.
    echo "Jira rejected the credentials for ${LUNAR_VAR_JIRA_USER}." >&2
    exit 1
    ;;
esac

# Write the ticket reference even when Jira could not confirm it, so an outage
# does not make the PR look ticket-less.
lunar collect ".vcs.pr.ticket.id" "$TICKET_KEY"
jq -n '{"tool": "jira", "integration": "api"}' | lunar collect -j ".vcs.pr.ticket.source" -

JIRA_BASE_URL="${LUNAR_VAR_JIRA_BASE_URL:-}"
if [ -n "$JIRA_BASE_URL" ]; then
  lunar collect ".vcs.pr.ticket.url" "${JIRA_BASE_URL%/}/browse/${TICKET_KEY}"
fi

if [ -z "$TICKET_VALID" ]; then
  # Exit 0, not 1: a non-zero exit makes the Hub discard every value collected
  # this run, erasing the ticket reference written above. tracker_error tells
  # the ticket-valid policy why .valid is missing; unset means validation was
  # never configured.
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

echo "$JIRA_RESPONSE" | lunar collect -j ".vcs.pr.ticket.native.jira" -
