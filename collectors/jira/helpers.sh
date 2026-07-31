#!/bin/bash
# helpers.sh — Shared ticket extraction logic for Jira collector sub-collectors.

# escape_string: Escapes special regex characters in a string for bash regex.
escape_string() {
  local str="$1"
  local escaped=""
  local i char
  for (( i=0; i<${#str}; i++ )); do
    char="${str:i:1}"
    case "$char" in
      \\|\.|\^|\$|\*|\+|\?|\(|\)|\[|\]|\{|\}|\||- ) escaped+="\\$char" ;;
      *) escaped+="$char" ;;
    esac
  done
  printf "%s" "$escaped"
}

# extract_ticket_id: Extracts a Jira ticket ID from PR text.
#
# Uses LUNAR_VAR_TICKET_PREFIX, LUNAR_VAR_TICKET_SUFFIX, and
# LUNAR_VAR_TICKET_PATTERN environment variables (from collector inputs).
#
# Arguments:
#   $@ - texts to search, in precedence order (PR title, then PR description)
#
# Outputs:
#   Prints the uppercase ticket key of the first text that matches, or nothing
#   if none do. Returns 0 if found, 1 if not found.
extract_ticket_id() {
  local prefix="${LUNAR_VAR_TICKET_PREFIX:-}"
  local suffix="${LUNAR_VAR_TICKET_SUFFIX:-}"
  local pattern="${LUNAR_VAR_TICKET_PATTERN:-[A-Za-z][A-Za-z0-9]+-[0-9]+}"

  local prefix_pattern suffix_pattern regex
  prefix_pattern="$(escape_string "$prefix")[[:space:]]*"
  suffix_pattern="[[:space:]]*$(escape_string "$suffix")"
  regex="${prefix_pattern}(${pattern})${suffix_pattern}"

  local text
  for text in "$@"; do
    if [[ $text =~ $regex ]]; then
      echo "${BASH_REMATCH[1]^^}"
      return 0
    fi
  done
  return 1
}

# fetch_pr_metadata: Fetches the PR title and description from GitHub API.
#
# Requires LUNAR_SECRET_GH_TOKEN, LUNAR_COMPONENT_ID, and LUNAR_COMPONENT_PR.
#
# Outputs:
#   Sets PR_TITLE and PR_BODY in the caller's scope; PR_BODY is empty when the
#   PR has no description. Returns 0 on success, 1 on failure.
fetch_pr_metadata() {
  # Component IDs are <host>/<owner>/<repository>[/<subpath>...]; monorepo
  # components append the component path after the repository. Keep only
  # owner/repository for the GitHub API URL.
  local host="${LUNAR_COMPONENT_ID%%/*}"
  local rest="${LUNAR_COMPONENT_ID#*/}"
  local owner="${rest%%/*}"
  rest="${rest#*/}"
  local repo="${owner}/${rest%%/*}"

  local api_url="https://api.github.com"
  if [ "$host" != "github.com" ]; then
    api_url="https://${host}/api/v3"
  fi

  set +e
  local response
  response="$(curl -fsS \
    -H 'Accept: application/vnd.github+json' \
    -H "Authorization: token ${LUNAR_SECRET_GH_TOKEN}" \
    "${api_url}/repos/${repo}/pulls/${LUNAR_COMPONENT_PR}")"
  local status=$?
  set -e

  if [ $status -ne 0 ] || [ -z "$response" ]; then
    echo "Unable to fetch PR ${LUNAR_COMPONENT_PR} metadata from GitHub." >&2
    return 1
  fi

  PR_TITLE="$(echo "$response" | jq -r '.title // empty')"
  PR_BODY="$(echo "$response" | jq -r '.body // empty')"
  if [ -z "$PR_TITLE" ]; then
    echo "Unable to parse PR ${LUNAR_COMPONENT_PR} title from GitHub response." >&2
    return 1
  fi
  return 0
}
