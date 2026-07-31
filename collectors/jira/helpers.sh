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

# extract_ticket_id: Extracts the first Jira ticket ID appearing in a text.
#
# Uses LUNAR_VAR_TICKET_PREFIX, LUNAR_VAR_TICKET_SUFFIX, and
# LUNAR_VAR_TICKET_PATTERN environment variables (from collector inputs).
#
# Arguments:
#   $1 - text to search
#
# Outputs:
#   Prints the uppercase ticket key to stdout, or nothing if not found.
#   Returns 0 if found, 1 if not found.
extract_ticket_id() {
  local text="$1"
  local prefix="${LUNAR_VAR_TICKET_PREFIX:-}"
  local suffix="${LUNAR_VAR_TICKET_SUFFIX:-}"
  local pattern="${LUNAR_VAR_TICKET_PATTERN:-[A-Za-z][A-Za-z0-9]+-[0-9]+}"

  local prefix_pattern suffix_pattern regex
  prefix_pattern="$(escape_string "$prefix")[[:space:]]*"
  suffix_pattern="[[:space:]]*$(escape_string "$suffix")"
  regex="${prefix_pattern}(${pattern})${suffix_pattern}"

  if [[ $text =~ $regex ]]; then
    echo "${BASH_REMATCH[1]^^}"
    return 0
  fi
  return 1
}

# extract_ticket_id_keyword: Extracts the ticket ID that a keyword marks as the
# text's own ticket, e.g. "Fixes ABC-123" or "Ticket: ABC-123".
#
# A PR description routinely names several tickets — dependencies, reverts,
# related work — so taking the first one that appears attributes the PR to
# whichever the author happened to mention first. Anchoring on a keyword picks
# the one they flagged as this PR's.
#
# Uses LUNAR_VAR_TICKET_KEYWORDS on top of the prefix/suffix/pattern variables.
# Keywords match case-insensitively.
#
# Arguments:
#   $1 - text to search
#
# Outputs:
#   Prints the uppercase ticket key to stdout, or nothing if the text has no
#   keyword-anchored reference. Returns 0 if found, 1 if not found.
extract_ticket_id_keyword() {
  local text="$1"
  local keywords="${LUNAR_VAR_TICKET_KEYWORDS:-fixes|fixed|fix|closes|closed|close|resolves|resolved|resolve|ticket|issue}"
  local prefix="${LUNAR_VAR_TICKET_PREFIX:-}"
  local suffix="${LUNAR_VAR_TICKET_SUFFIX:-}"
  local pattern="${LUNAR_VAR_TICKET_PATTERN:-[A-Za-z][A-Za-z0-9]+-[0-9]+}"

  # Group 1 is the leading boundary (keeps "prefixes" from matching "fixes"),
  # group 2 the keyword, group 3 the ticket key. A caller-supplied pattern may
  # add groups of its own, but they can only open after group 3.
  local regex
  regex="(^|[^[:alnum:]])(${keywords})[[:space:]:]+"
  regex+="$(escape_string "$prefix")[[:space:]]*(${pattern})"
  regex+="[[:space:]]*$(escape_string "$suffix")"

  local restore key=""
  restore="$(shopt -p nocasematch)"
  shopt -s nocasematch
  if [[ $text =~ $regex ]]; then
    key="${BASH_REMATCH[3]^^}"
  fi
  eval "$restore"

  if [ -n "$key" ]; then
    echo "$key"
    return 0
  fi
  return 1
}

# resolve_ticket_id: Resolves the PR's ticket ID from PR_TITLE and PR_BODY,
# which fetch_pr_metadata populates.
#
# Precedence:
#   1. The PR title.
#   2. A keyword-anchored reference in the description ("Fixes ABC-123").
#   3. The first bare reference in the description.
#
# Outputs:
#   Prints the uppercase ticket key to stdout, or nothing if the PR references
#   no ticket. Returns 0 if found, 1 if not found.
resolve_ticket_id() {
  extract_ticket_id "$PR_TITLE" && return 0
  extract_ticket_id_keyword "$PR_BODY" && return 0
  extract_ticket_id "$PR_BODY"
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
