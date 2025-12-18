#!/bin/bash
set -e

# Set these to control how your Jira ticket IDs look in PR titles.
# For example, set these to square brackets if your ticket format looks like: "[ABC-123] PR Title"
JIRA_TICKET_PREFIX="["
JIRA_TICKET_SUFFIX="]"

# Configure these to match your Jira instance.
# Note that LUNAR_COLLECTOR_SECRET_JIRA_TOKEN must also be set in lunar collector secrets, 
# and it must correspond to the LUNAR_JIRA_USER below.
LUNAR_JIRA_BASE_URL=https://earthly.atlassian.net
LUNAR_JIRA_USER=brandon@earthly.dev

if [ -z "${LUNAR_COMPONENT_PR:-}" ]; then
  # Only run inside PR contexts.
  echo "Not in a PR"
  exit 0
fi

if [ -z "${LUNAR_SECRET_GH_TOKEN:-}" ]; then
  echo "Jira collector requires LUNAR_SECRET_GH_TOKEN to query GitHub." >&2
  exit 0
fi

REPO="${LUNAR_COMPONENT_ID#github.com/}"

set +e
PR_RESPONSE="$(curl -fsS \
  -H 'Accept: application/vnd.github+json' \
  -H "Authorization: token ${LUNAR_SECRET_GH_TOKEN}" \
  "https://api.github.com/repos/${REPO}/pulls/${LUNAR_COMPONENT_PR}")"
CURL_STATUS=$?
set -e

if [ $CURL_STATUS -ne 0 ] || [ -z "$PR_RESPONSE" ]; then
  echo "Unable to fetch PR ${LUNAR_COMPONENT_PR} metadata from GitHub." >&2
  exit 0
fi

PR_TITLE="$(echo "$PR_RESPONSE" | jq -r '.title // empty')"

if [ -z "$PR_TITLE" ]; then
  exit 0
fi

escape_char() {
  local char="$1"
  case "$char" in
    "" ) printf "" ;;
    \.|\^|\$|\*|\+|\?|\(|\)|\[|\]|\{|\}|\||- ) printf "\\%s" "$char" ;;
    *) printf "%s" "$char" ;;
  esac
}

ticket_pattern="([A-Za-z][A-Za-z0-9]+-[0-9]+)"
prefix_pattern="$(escape_char "$JIRA_TICKET_PREFIX")[[:space:]]*"
suffix_pattern="[[:space:]]*$(escape_char "$JIRA_TICKET_SUFFIX")"

regex="${prefix_pattern}${ticket_pattern}${suffix_pattern}"
TICKET_KEY=""
if [[ $PR_TITLE =~ $regex ]]; then
  TICKET_KEY="${BASH_REMATCH[1]^^}"
fi

if [ -z "$TICKET_KEY" ]; then
  exit 0
fi

if [ -z "${LUNAR_JIRA_BASE_URL:-}" ]; then
  echo "Jira collector requires LUNAR_JIRA_BASE_URL to be set." >&2
  exit 0
fi

if [ -z "${LUNAR_JIRA_USER:-}" ]; then
  echo "Jira collector requires LUNAR_JIRA_USER to be set." >&2
  exit 0
fi

if [ -z "${LUNAR_SECRET_JIRA_TOKEN:-}" ]; then
  echo "Jira collector requires LUNAR_SECRET_JIRA_TOKEN to be set." >&2
  exit 0
fi

JIRA_API_URL="${LUNAR_JIRA_BASE_URL%/}/rest/api/3/issue/${TICKET_KEY}"

set +e
JIRA_RESPONSE="$(curl -fsS \
  -u "${LUNAR_JIRA_USER}:${LUNAR_SECRET_JIRA_TOKEN}" \
  -H 'Accept: application/json' \
  "$JIRA_API_URL")"
CURL_STATUS=$?
set -e

if [ $CURL_STATUS -ne 0 ] || [ -z "$JIRA_RESPONSE" ]; then
  echo "Unable to fetch Jira issue ${TICKET_KEY} from ${LUNAR_JIRA_BASE_URL}." >&2
  exit 0
fi

echo "$JIRA_RESPONSE" | lunar collect -j ".jira.ticket" -

