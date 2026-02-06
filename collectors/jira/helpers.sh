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

# extract_ticket_id: Extracts a Jira ticket ID from a PR title.
#
# Uses LUNAR_VAR_TICKET_PREFIX, LUNAR_VAR_TICKET_SUFFIX, and
# LUNAR_VAR_TICKET_PATTERN environment variables (from collector inputs).
#
# Arguments:
#   $1 - PR title string
#
# Outputs:
#   Prints the uppercase ticket key to stdout, or nothing if not found.
#   Returns 0 if found, 1 if not found.
extract_ticket_id() {
  local pr_title="$1"
  local prefix="${LUNAR_VAR_TICKET_PREFIX:-[}"
  local suffix="${LUNAR_VAR_TICKET_SUFFIX:-]}"
  local pattern="${LUNAR_VAR_TICKET_PATTERN:-[A-Za-z][A-Za-z0-9]+-[0-9]+}"

  local prefix_pattern suffix_pattern regex
  prefix_pattern="$(escape_string "$prefix")[[:space:]]*"
  suffix_pattern="[[:space:]]*$(escape_string "$suffix")"
  regex="${prefix_pattern}(${pattern})${suffix_pattern}"

  if [[ $pr_title =~ $regex ]]; then
    echo "${BASH_REMATCH[1]^^}"
    return 0
  fi
  return 1
}

# fetch_pr_title: Fetches the PR title from GitHub API.
#
# Requires LUNAR_SECRET_GH_TOKEN, LUNAR_COMPONENT_ID, and LUNAR_COMPONENT_PR.
#
# Outputs:
#   Prints the PR title to stdout, or nothing on failure.
#   Returns 0 on success, 1 on failure.
fetch_pr_title() {
  local repo="${LUNAR_COMPONENT_ID#github.com/}"

  set +e
  local response
  response="$(curl -fsS \
    -H 'Accept: application/vnd.github+json' \
    -H "Authorization: token ${LUNAR_SECRET_GH_TOKEN}" \
    "https://api.github.com/repos/${repo}/pulls/${LUNAR_COMPONENT_PR}")"
  local status=$?
  set -e

  if [ $status -ne 0 ] || [ -z "$response" ]; then
    echo "Unable to fetch PR ${LUNAR_COMPONENT_PR} metadata from GitHub." >&2
    return 1
  fi

  local title
  title="$(echo "$response" | jq -r '.title // empty')"
  if [ -z "$title" ]; then
    return 1
  fi
  echo "$title"
  return 0
}
