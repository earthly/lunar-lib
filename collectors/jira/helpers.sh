#!/bin/bash
# helpers.sh — Shared ticket resolution logic for Jira collector sub-collectors.

DEFAULT_TICKET_PATTERN="[A-Za-z][A-Za-z0-9]+-[0-9]+"
DEFAULT_TICKET_KEYWORDS="fixes|fixed|fix|closes|closed|close|resolves|resolved|resolve|ticket|issue"

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

# any_case: Rewrites each ASCII letter as a bracket expression so the pattern
# matches either case. Regex metacharacters, notably the | separating the
# keywords, pass through untouched.
#
# This is done by construction rather than with nocasematch because scan_all
# walks a text by cutting each match off the front, and nocasematch loosens
# that cut too — it could land on an earlier, differently-cased occurrence and
# re-match the same text forever.
any_case() {
  local str="$1"
  local out=""
  local i char
  for (( i=0; i<${#str}; i++ )); do
    char="${str:i:1}"
    case "$char" in
      [A-Za-z]) out+="[${char,,}${char^^}]" ;;
      *) out+="$char" ;;
    esac
  done
  printf "%s" "$out"
}

# bare_ticket_regex: Matches a ticket key wherever it appears, with the
# configured prefix/suffix around it. Ticket key in group 1.
bare_ticket_regex() {
  local prefix suffix
  prefix="$(escape_string "${LUNAR_VAR_TICKET_PREFIX:-}")[[:space:]]*"
  suffix="[[:space:]]*$(escape_string "${LUNAR_VAR_TICKET_SUFFIX:-}")"
  printf "%s(%s)%s" "$prefix" "${LUNAR_VAR_TICKET_PATTERN:-$DEFAULT_TICKET_PATTERN}" "$suffix"
}

# keyword_ticket_regex: Matches a ticket key that a keyword marks as the text's
# own ticket, e.g. "Fixes ABC-123" or "Ticket: ABC-123". Group 1 is the
# keyword, group 2 the ticket key. A caller-supplied pattern may add groups of
# its own, but they can only open after group 2.
#
# \b keeps a word like "prefixes" from registering as the "fixes" keyword.
keyword_ticket_regex() {
  local keywords prefix suffix
  keywords="$(any_case "${LUNAR_VAR_TICKET_KEYWORDS:-$DEFAULT_TICKET_KEYWORDS}")"
  prefix="$(escape_string "${LUNAR_VAR_TICKET_PREFIX:-}")[[:space:]]*"
  suffix="[[:space:]]*$(escape_string "${LUNAR_VAR_TICKET_SUFFIX:-}")"
  printf "\\\\b(%s)[[:space:]:]+%s(%s)%s" \
    "$keywords" "$prefix" "${LUNAR_VAR_TICKET_PATTERN:-$DEFAULT_TICKET_PATTERN}" "$suffix"
}

# scan_all: Prints every match of a regex in a text, uppercased, one per line,
# in the order they appear.
#
# Arguments:
#   $1 - text to search
#   $2 - regex
#   $3 - capture group holding the ticket key
scan_all() {
  local text="$1"
  local regex="$2"
  local group="$3"
  local matched prefix
  while [[ $text =~ $regex ]]; do
    matched="${BASH_REMATCH[0]}"
    if [ -z "$matched" ]; then
      break
    fi
    printf "%s\n" "${BASH_REMATCH[$group]^^}"
    prefix="${text%%"$matched"*}"
    text="${text:$(( ${#prefix} + ${#matched} ))}"
  done
}

# list_ticket_candidates: Prints the PR's candidate ticket keys, best first,
# from PR_TITLE and PR_BODY as fetch_pr_metadata populates them.
#
# Order:
#   1. Every bare reference in the title — a title reference always wins.
#   2. Every keyword-anchored reference in the description. A description
#      usually names several tickets, and the first to appear is often a
#      dependency rather than the PR's own, so a flagged one outranks it.
#   3. Every bare reference in the description.
#
# Repeats are dropped, keeping the best position. The list is capped because
# each candidate costs a Jira lookup and a description can name arbitrarily
# many tokens that look like keys.
list_ticket_candidates() {
  local bare keyword
  bare="$(bare_ticket_regex)"
  keyword="$(keyword_ticket_regex)"

  {
    scan_all "$PR_TITLE" "$bare" 1
    scan_all "$PR_BODY" "$keyword" 2
    scan_all "$PR_BODY" "$bare" 1
  } | awk '!seen[$0]++' | head -n "${LUNAR_VAR_MAX_TICKET_CANDIDATES:-5}"
}

# jira_validation_configured: True when the inputs and secret needed to reach
# the Jira API are all set.
jira_validation_configured() {
  [ -n "${LUNAR_VAR_JIRA_BASE_URL:-}" ] &&
    [ -n "${LUNAR_VAR_JIRA_USER:-}" ] &&
    [ -n "${LUNAR_SECRET_JIRA_TOKEN:-}" ]
}

# jira_validate_ticket: Looks a ticket key up in the Jira REST API.
#
# curl retries the transient failures itself — connection refused, timeouts,
# 429 and 5xx. --retry-all-errors is deliberately not used: it would also retry
# the 404 and 401 that this function exists to tell apart.
#
# Arguments:
#   $1 - ticket key
#
# Outputs:
#   Sets JIRA_RESPONSE to the raw issue JSON when the ticket exists. Returns:
#     0 - the ticket exists
#     1 - the ticket does not exist
#     2 - Jira rejected the credentials
#     3 - Jira stayed unreachable across every retry
jira_validate_ticket() {
  local key="$1"
  local url="${LUNAR_VAR_JIRA_BASE_URL%/}/rest/api/3/issue/${key}"
  local body_file http_code status

  body_file="$(mktemp)"
  set +e
  http_code="$(curl -sS \
    --retry "${LUNAR_VAR_JIRA_RETRIES:-3}" \
    --retry-delay 2 \
    --retry-max-time 60 \
    --retry-connrefused \
    --max-time 30 \
    -o "$body_file" \
    -w '%{http_code}' \
    -u "${LUNAR_VAR_JIRA_USER}:${LUNAR_SECRET_JIRA_TOKEN}" \
    -H 'Accept: application/json' \
    "$url")"
  status=$?
  set -e

  JIRA_RESPONSE="$(cat "$body_file")"
  rm -f "$body_file"

  if [ $status -ne 0 ]; then
    JIRA_RESPONSE=""
    return 3
  fi

  case "$http_code" in
    200)
      if [ -n "$JIRA_RESPONSE" ]; then
        return 0
      fi
      ;;
    401|403)
      JIRA_RESPONSE=""
      return 2
      ;;
    404)
      JIRA_RESPONSE=""
      return 1
      ;;
  esac

  JIRA_RESPONSE=""
  return 3
}

# resolve_ticket: Resolves the PR's ticket, validating candidates against Jira
# in order and taking the first one that exists.
#
# A candidate Jira does not know is a false positive rather than the PR's
# ticket — the default pattern matches tokens like UTF-8 or SHA-256, which are
# common in descriptions — so resolution moves on to the next candidate.
# Without Jira configured there is nothing to validate against, so the best
# candidate is taken as-is.
#
# Outputs:
#   Sets TICKET_KEY, TICKET_VALID ("true" only when Jira confirmed the ticket),
#   TICKET_ERROR ("unreachable" or "not_found" when validation ran and settled
#   nothing), and JIRA_RESPONSE for a confirmed ticket. Returns:
#     0 - the PR references a candidate; see TICKET_VALID for its standing
#     1 - the PR references no candidate at all
#     2 - Jira rejected the credentials
resolve_ticket() {
  TICKET_KEY=""
  TICKET_VALID=""
  TICKET_ERROR=""
  JIRA_RESPONSE=""

  local candidates key rc
  mapfile -t candidates < <(list_ticket_candidates)
  if [ ${#candidates[@]} -eq 0 ]; then
    return 1
  fi

  TICKET_KEY="${candidates[0]}"
  if ! jira_validation_configured; then
    return 0
  fi

  for key in "${candidates[@]}"; do
    rc=0
    jira_validate_ticket "$key" || rc=$?
    case $rc in
      0)
        TICKET_KEY="$key"
        TICKET_VALID="true"
        return 0
        ;;
      1)
        echo "Jira does not know ${key}, trying the next candidate." >&2
        ;;
      2)
        return 2
        ;;
      *)
        # Every candidate before this one came back a definitive 404, so this
        # is the best one still standing. Reporting candidates[0] here would
        # name a key Jira already denied and blame the outage for it.
        echo "Jira unreachable while looking up ${key}." >&2
        TICKET_KEY="$key"
        TICKET_ERROR="unreachable"
        return 0
        ;;
    esac
  done

  TICKET_ERROR="not_found"
  return 0
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
