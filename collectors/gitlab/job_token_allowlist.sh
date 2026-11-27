#!/bin/bash

# LUNAR_COMPONENT_ID / LUNAR_COMPONENT_META / LUNAR_SECRET_* / LUNAR_VAR_* are
# injected by the Lunar runtime — they are not local assignments or typos.
# shellcheck disable=SC2153
set -euo pipefail

# Records whether the project limits which other projects' CI/CD job tokens can
# access it (Settings > CI/CD > Job token permissions: the CI/CD job token
# allowlist), with one read: GET /projects/:id/job_token_scope -> inbound_enabled.
#
# GitLab answers only Maintainers, so a denied read is common. 403 and 404 are
# stable per project and are recorded as .error, never as enabled or disabled.
# 401, 429, 5xx, network failures and unreadable answers write nothing and exit
# 1: a bad token or an outage must not replace an earlier good result.

GITLAB_HOST="${LUNAR_VAR_GITLAB_HOST:-gitlab.com}"
HOST="${LUNAR_COMPONENT_ID%%/*}"

if [ "$HOST" != "$GITLAB_HOST" ]; then
  echo "Skipping: LUNAR_COMPONENT_ID host '${HOST:-<unset>}' != gitlab_host '${GITLAB_HOST}'." >&2
  exit 0
fi

# GL_JOB_TOKEN_SCOPE_TOKEN is for a fine-grained token limited to these reads; a
# read_api token on a Maintainer could also read the project's CI/CD variables.
if [ -n "${LUNAR_SECRET_GL_JOB_TOKEN_SCOPE_TOKEN:-}" ]; then
  TOKEN="$LUNAR_SECRET_GL_JOB_TOKEN_SCOPE_TOKEN"
  TOKEN_NAME=GL_JOB_TOKEN_SCOPE_TOKEN
elif [ -n "${LUNAR_SECRET_GL_TOKEN:-}" ]; then
  TOKEN="$LUNAR_SECRET_GL_TOKEN"
  TOKEN_NAME=GL_TOKEN
else
  echo "Error: LUNAR_SECRET_GL_TOKEN is not set. Configure the GL_TOKEN secret (or GL_JOB_TOKEN_SCOPE_TOKEN) for this collector." >&2
  exit 1
fi

PROJECT_PATH="${LUNAR_COMPONENT_ID#*/}"
# The gitlab cataloger's meta.project_id survives renames and moves; the path
# is the fallback for components it didn't catalog.
PROJECT_ID=$(printf '%s' "${LUNAR_COMPONENT_META:-}" | jq -r '.project_id // empty | tostring' 2>/dev/null || true)
if [[ "$PROJECT_ID" =~ ^[0-9]+$ ]]; then
  PROJECT_REF="$PROJECT_ID"
else
  PROJECT_ID=""
  PROJECT_REF=$(printf '%s' "$PROJECT_PATH" | sed 's#/#%2F#g')
fi
API_BASE="https://${HOST}/api/v4"

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

# gl_get <path>: sets GL_CODE (HTTP status, 000 when no response arrived) and
# GL_BODY. Retries 000, 429 and 5xx up to 3 attempts, waiting Retry-After when
# GitLab sends one (at most 60 s). Never retries 401, 403 or 404.
gl_get() {
  local attempt=1 delay
  while :; do
    : > "$WORK/body"
    : > "$WORK/headers"
    GL_CODE=$(curl -sS --max-time 30 -o "$WORK/body" -D "$WORK/headers" -w '%{http_code}' \
      -H "PRIVATE-TOKEN: ${TOKEN}" "${API_BASE}$1" 2> "$WORK/curl.err") || GL_CODE=000
    GL_BODY=$(cat "$WORK/body")
    case "$GL_CODE" in
      000 | 429 | 5[0-9][0-9])
        if [ "$attempt" -lt 3 ]; then
          delay=$(sed -n 's/^[Rr]etry-[Aa]fter:[[:space:]]*\([0-9][0-9]*\).*/\1/p' "$WORK/headers" | tail -n 1)
          [ -n "$delay" ] || delay="$attempt"
          [ "$delay" -le 60 ] || delay=60
          echo "HTTP $GL_CODE on $1 (attempt $attempt/3), retrying in ${delay}s." >&2
          sleep "$delay"
          attempt=$((attempt + 1))
          continue
        fi
        ;;
    esac
    return 0
  done
}

# gl_list <path>: sets GL_LIST to every entry of a paginated list. Returns 1 on
# a failed or non-list page, or after 5 full pages, when the list might go on.
# GitLab caps each allowlist at 200 entries.
gl_list() {
  local page=1 count
  GL_LIST='[]'
  while [ "$page" -le 5 ]; do
    gl_get "$1?per_page=100&page=${page}"
    [ "$GL_CODE" = "200" ] || return 1
    count=$(printf '%s' "$GL_BODY" | jq 'if type == "array" then length else error("not a list") end' 2> /dev/null) || return 1
    GL_LIST=$(printf '%s\n%s\n' "$GL_LIST" "$GL_BODY" | jq -cs 'add')
    [ "$count" -lt 100 ] && return 0
    page=$((page + 1))
  done
  return 1
}

body_excerpt() { printf '%s' "$GL_BODY" | head -c 300; }

collect() {
  printf '%s' "$1" | lunar collect -j ".vcs.job_token_allowlist" -
}

gl_get "/projects/${PROJECT_REF}/job_token_scope"
CHECKED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)

case "$GL_CODE" in
  200) ;;
  403)
    echo "GitLab denied the job token scope read for ${PROJECT_PATH} (HTTP 403): ${TOKEN_NAME}'s user isn't a Maintainer. Recording it as unknown. If you grant the role, use a fine-grained token in GL_JOB_TOKEN_SCOPE_TOKEN: a read_api token on a Maintainer can also read CI/CD variables." >&2
    collect "$(jq -n --arg at "$CHECKED_AT" '{error: "forbidden", checked_at: $at}')"
    exit 0
    ;;
  404)
    echo "GitLab returned 404 for ${PROJECT_PATH}: the project is gone or the token can't see it. Recording it as unknown." >&2
    collect "$(jq -n --arg at "$CHECKED_AT" '{error: "not_found", checked_at: $at}')"
    exit 0
    ;;
  401)
    echo "Error: GitLab rejected ${TOKEN_NAME} (HTTP 401). Nothing recorded. $(body_excerpt)" >&2
    exit 1
    ;;
  000)
    echo "Error: no response from ${API_BASE} after 3 attempts. Nothing recorded. $(head -c 300 "$WORK/curl.err")" >&2
    exit 1
    ;;
  *)
    echo "Error: HTTP $GL_CODE reading the job token scope of ${PROJECT_PATH}. Nothing recorded. $(body_excerpt)" >&2
    exit 1
    ;;
esac

ENABLED=$(printf '%s' "$GL_BODY" | jq -r 'if type == "object" and (.inbound_enabled | type) == "boolean" then .inbound_enabled else "invalid" end' 2> /dev/null || echo invalid)
case "$ENABLED" in
  false)
    echo "Job token allowlist is off for ${PROJECT_PATH}." >&2
    collect "$(jq -n --arg at "$CHECKED_AT" '{enabled: false, checked_at: $at}')"
    exit 0
    ;;
  true) ;;
  *)
    echo "Error: GitLab's job token scope answer for ${PROJECT_PATH} has no boolean inbound_enabled. Nothing recorded. $(body_excerpt)" >&2
    exit 1
    ;;
esac

# Enabled: count the entries. A count that can't be read is left out; the
# setting itself is known. The project list always includes the project itself.
PROJECT_COUNT=null
if gl_list "/projects/${PROJECT_REF}/job_token_scope/allowlist"; then
  PROJECT_COUNT=$(printf '%s' "$GL_LIST" | jq --arg id "$PROJECT_ID" --arg path "$PROJECT_PATH" '
    [ .[] | select(if $id != "" then (.id | tostring) == $id
                   else ((.path_with_namespace // "") | ascii_downcase) == ($path | ascii_downcase) end) ] as $self
    | if ($self | length) == 1 then length - 1 else null end')
  [ "$PROJECT_COUNT" != "null" ] || echo "Allowlist doesn't list ${PROJECT_PATH} itself exactly once; leaving out the project count." >&2
else
  echo "Couldn't read the whole project allowlist (last HTTP status $GL_CODE); leaving out the project count." >&2
fi
GROUP_COUNT=null
if gl_list "/projects/${PROJECT_REF}/job_token_scope/groups_allowlist"; then
  GROUP_COUNT=$(printf '%s' "$GL_LIST" | jq 'length')
else
  echo "Couldn't read the whole group allowlist (last HTTP status $GL_CODE); leaving out the group count." >&2
fi

echo "Job token allowlist is on for ${PROJECT_PATH} (other projects: ${PROJECT_COUNT}, groups: ${GROUP_COUNT})." >&2
collect "$(jq -n --argjson projects "$PROJECT_COUNT" --argjson groups "$GROUP_COUNT" --arg at "$CHECKED_AT" '
  {enabled: true}
  + (if $projects != null then {projects: $projects} else {} end)
  + (if $groups != null then {groups: $groups} else {} end)
  + {checked_at: $at}')"
