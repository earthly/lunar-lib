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

# The read races the record that dispatched this run, so in PR context it is
# RETRIED.
#
# The after-json wave fires off the LIVE merged blob the instant .vcs.pr.title
# lands, but `lunar component get-json` resolves through a copy the Hub's mat
# workers drain asynchronously — so this collector can be dispatched by a record
# it cannot yet read.
#
# Here the trigger path IS the input: the hook is `after-json` on .vcs.pr.title,
# and the Hub dispatches only collectors whose path is PRESENT in that live blob.
# So in PR context a missing title cannot mean "this PR has no title" — it means
# the read is behind the record that triggered the run. Retry it, and FAIL
# rather than skip if it never arrives: the wave is fire-once per
# (component, sha), so a swallowed read loses this PR's ticket permanently and
# no re-run recovers it.
#
# Outside PR context nothing changes. A branch push has no .vcs.pr.title for the
# hook to match, so the wave does not fire there at all — that path is only
# reached by a manual/dev run, where an absent title is genuine and skipping is
# right.
#
# The _TEST_ override is a test seam, deliberately NOT declared in `inputs:`.
READ_BUDGET_SECS="${LUNAR_JIRA_TEST_READ_BUDGET:-900}"
BACKOFF_STEP="${LUNAR_JIRA_TEST_BACKOFF_STEP:-5}"
[ -n "${LUNAR_COMPONENT_PR:-}" ] || READ_BUDGET_SECS=0

# Disposable container, so a fixed path needs no mktemp and no cleanup.
GETJSON_ERR=/tmp/get-json.err
JQ_ERR=/tmp/jq.err
ATTEMPT=0
WAITED=0
while :; do
  ATTEMPT=$((ATTEMPT + 1))
  if COMPONENT_JSON=$(lunar component get-json "$LUNAR_COMPONENT_ID" "${pr_arg[@]}" 2>"$GETJSON_ERR"); then
    # `set -e` is on and there is no pipefail, so an assignment from a failing
    # jq would abort the script here on jq's bare exit status — no retry, no
    # explanation. An unparseable blob is one of the shapes this fix exists to
    # make visible, so surface jq's error and let the retry below decide.
    if ! PR_TITLE=$(printf '%s' "$COMPONENT_JSON" | jq -r '.vcs.pr.title // empty' 2>"$JQ_ERR"); then
      PR_TITLE=""
      if [ "$ATTEMPT" -eq 1 ] && [ -s "$JQ_ERR" ]; then
        sed 's/^/  jq: /' "$JQ_ERR" >&2
      fi
    fi
  else
    COMPONENT_JSON=""
    PR_TITLE=""
    # Surface the CLI's own error instead of discarding it — `2>/dev/null ||
    # echo ""` turned a broken read into a clean-looking skip. Once, not once
    # per attempt; the error itself, not cobra's usage block.
    if [ "$ATTEMPT" -eq 1 ] && [ -s "$GETJSON_ERR" ]; then
      sed -n '/^Usage:/q;p' "$GETJSON_ERR" | head -c 500 | sed 's/^/  get-json: /' >&2
    fi
  fi
  [ -n "$PR_TITLE" ] && break
  BACKOFF=$((ATTEMPT * BACKOFF_STEP))
  [ "$BACKOFF" -gt $((BACKOFF_STEP * 6)) ] && BACKOFF=$((BACKOFF_STEP * 6))
  [ $((WAITED + BACKOFF)) -gt "$READ_BUDGET_SECS" ] && break
  sleep "$BACKOFF"
  WAITED=$((WAITED + BACKOFF))
done
if [ "$WAITED" -gt 0 ]; then
  echo "Waited ${WAITED}s across ${ATTEMPT} attempt(s) for .vcs.pr.title to become readable." >&2
fi

# PR_BODY is consumed by resolve_ticket/list_ticket_candidates in helpers.sh.
# The `|| PR_BODY=""` is load-bearing, not defensive noise: an unparseable blob
# leaves PR_TITLE empty above without aborting, so this jq can still fail — and
# under `set -e` an unhandled failing assignment would exit here on jq's bare
# status, skipping the diagnosis below entirely.
# shellcheck disable=SC2034
PR_BODY=$(printf '%s' "$COMPONENT_JSON" | jq -r '.vcs.pr.description // empty' 2>/dev/null) || PR_BODY=""

if [ -z "$PR_TITLE" ]; then
  if [ -n "${LUNAR_COMPONENT_PR:-}" ]; then
    echo "No .vcs.pr.title for ${LUNAR_COMPONENT_ID:-?} PR ${LUNAR_COMPONENT_PR} after ${WAITED}s across ${ATTEMPT} attempt(s). The after-json hook on .vcs.pr.title only fires when that path is present, so the read is behind the record that dispatched this run rather than the title being absent." >&2
    echo "Failing the run: the wave is fire-once per (component, sha), so this PR's ticket is lost and no re-run recovers it." >&2
    exit 1
  fi
  echo "No .vcs.pr.title in Component JSON and not a PR run (PR-metadata collector not run yet?), skipping." >&2
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
