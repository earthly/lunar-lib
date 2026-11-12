#!/bin/bash

# LUNAR_COMPONENT_ID / LUNAR_COMPONENT_PR / LUNAR_SECRET_* are injected by the
# Lunar runtime — they are not local assignments or typos of each other.
# shellcheck disable=SC2153
set -e

# Reads the check run SonarQube (Server or Cloud) posts on a pull request's head
# commit, on github.com or GitHub Enterprise Server, and records the quality
# gate and the PR's new-code numbers from it (github-app.jq). Polls up to
# github_app_poll_timeout_seconds, because SonarQube posts the check only after
# its analysis completes; on timeout writes
# .code_quality.native.sonarqube.github_app.status = "pending".

HERE="$(dirname "$0")"
# shellcheck source=collectors/sonarqube/helpers.sh disable=SC1091
source "$HERE/helpers.sh"

if [ -z "${LUNAR_COMPONENT_PR:-}" ]; then
    echo "sonarqube/github-app: not a pull request — skipping." >&2
    exit 0
fi
if [ -z "${LUNAR_COMPONENT_GIT_SHA:-}" ]; then
    echo "sonarqube/github-app: no head SHA — skipping." >&2
    exit 0
fi

# Component IDs are <host>/<owner>/<repository>[/<subpath>...]. Keep only
# owner/repository, and route GHES hosts to /api/v3.
case "${LUNAR_COMPONENT_ID:-}" in
    */*/*) ;;
    *) echo "sonarqube/github-app: component id '${LUNAR_COMPONENT_ID:-}' isn't <host>/<owner>/<repository> — skipping." >&2; exit 0 ;;
esac
HOST="${LUNAR_COMPONENT_ID%%/*}"
REST="${LUNAR_COMPONENT_ID#*/}"
OWNER="${REST%%/*}"
REST="${REST#*/}"
REPO="${OWNER}/${REST%%/*}"
# A hub can serve GitLab too: never send a GitHub token there.
case "$HOST" in
    *gitlab*) echo "sonarqube/github-app: GitHub only; $HOST is not supported — skipping." >&2; exit 0 ;;
esac
API_BASE="https://api.github.com"
if [ "$HOST" != "github.com" ]; then
    API_BASE="https://${HOST}/api/v3"
fi

# With github_app set, mint a token from that Hub GitHub App (`lunar github-app add`),
# for the component's host and owner, instead of using a secret. The token asks for
# only the permission this script uses, so an App without it falls back to the
# secret; github_app_only turns that off. GHES prefers GH_ENTERPRISE_TOKEN.
mint_app_token() {
    [ -n "${LUNAR_VAR_GITHUB_APP:-}" ] && APP_TOKEN=$(lunar github-app get-token "$LUNAR_VAR_GITHUB_APP" --permission checks=read) \
        && [ -n "$APP_TOKEN" ]
}
TOKEN=""
FROM_APP=false
SECRET="GH_TOKEN"
[ "$HOST" = "github.com" ] || SECRET="GH_ENTERPRISE_TOKEN (or GH_TOKEN)"
if mint_app_token; then
    echo "GitHub auth: GitHub App $LUNAR_VAR_GITHUB_APP" >&2
    TOKEN="$APP_TOKEN"
    FROM_APP=true
elif [ "${LUNAR_VAR_GITHUB_APP_ONLY:-false}" = "true" ]; then
    echo "GitHub auth: no token from GitHub App ${LUNAR_VAR_GITHUB_APP:-(github_app is not set)}, and github_app_only is set" >&2
    exit 1
elif [ -n "${LUNAR_VAR_GITHUB_APP:-}" ]; then
    echo "GitHub auth: $SECRET secret, because GitHub App $LUNAR_VAR_GITHUB_APP minted no token" >&2
fi
if [ -z "$TOKEN" ]; then
    if [ "$HOST" = "github.com" ]; then
        TOKEN="${LUNAR_SECRET_GH_TOKEN:-}"
    else
        TOKEN="${LUNAR_SECRET_GH_ENTERPRISE_TOKEN:-${LUNAR_SECRET_GH_TOKEN:-}}"
    fi
fi
if [ -z "$TOKEN" ]; then
    echo "sonarqube/github-app: no $SECRET secret for $HOST — skipping." >&2
    exit 0
fi

TIMEOUT="${LUNAR_VAR_GITHUB_APP_POLL_TIMEOUT_SECONDS:-180}"
INTERVAL="${LUNAR_VAR_GITHUB_APP_POLL_INTERVAL_SECONDS:-10}"
case "$TIMEOUT" in ''|*[!0-9]*) echo "sonarqube/github-app: github_app_poll_timeout_seconds must be a number of seconds, got '$TIMEOUT'" >&2; exit 1 ;; esac
case "$INTERVAL" in ''|*[!0-9]*) echo "sonarqube/github-app: github_app_poll_interval_seconds must be a number of seconds, got '$INTERVAL'" >&2; exit 1 ;; esac
# Base 10, or bash reads a leading 0 as octal ("08" is an error).
TIMEOUT=$((10#$TIMEOUT))
INTERVAL=$((10#$INTERVAL))
if [ "$INTERVAL" -eq 0 ]; then
    echo "sonarqube/github-app: github_app_poll_interval_seconds must be more than 0" >&2
    exit 1
fi
PROJECT_KEY="$(sq_project_key)"
WORK="$(mktemp -d)"

# Every check run on the commit, including superseded ones: a later branch
# analysis of the same commit can share the PR check's name. Writes them to
# $WORK/runs.json. Returns 1 on a transient failure, 2 on anything else, with
# the status in FETCH_CODE and the reason in FETCH_ERR.
fetch_check_runs() {
    local page=1 url resp body
    : > "$WORK/pages"
    while [ "$page" -le 10 ]; do
        url="${API_BASE}/repos/${REPO}/commits/${LUNAR_COMPONENT_GIT_SHA}/check-runs?filter=all&per_page=100&page=${page}"
        resp=$(curl -sSL -w $'\n%{http_code}' \
            -H "Accept: application/vnd.github+json" \
            -H "Authorization: token ${TOKEN}" \
            -H "X-GitHub-Api-Version: 2022-11-28" \
            "$url" 2>/dev/null) || resp=$'\n000'
        FETCH_CODE="${resp##*$'\n'}"
        body="${resp%$'\n'*}"
        if [ "$FETCH_CODE" != "200" ]; then
            FETCH_ERR="HTTP $FETCH_CODE from ${url%%\?*}$(printf '%s' "$body" | jq -r '.message? // empty | ": " + .' 2>/dev/null | head -c 200)"
            case "$FETCH_CODE" in
                000 | 429 | 5[0-9][0-9]) return 1 ;;
                403) printf '%s' "$body" | grep -qi 'rate limit' && return 1 ;;
            esac
            return 2
        fi
        if ! printf '%s' "$body" | jq -ce '.check_runs | arrays' >> "$WORK/pages" 2>/dev/null; then
            FETCH_ERR="unreadable response from ${url%%\?*}"
            return 1
        fi
        [ "$(printf '%s' "$body" | jq '.check_runs | length')" -lt 100 ] && break
        page=$((page + 1))
    done
    jq -cs 'add // []' "$WORK/pages" > "$WORK/runs.json" || { FETCH_ERR="unreadable check runs"; return 1; }
}

# Poll now and every interval until the timeout, the last poll at the deadline.
ELAPSED=0
SEEN=false
REMINTED=false
STATE="no response from GitHub"
RESULT='{"done":false}'
while :; do
    set +e
    fetch_check_runs
    rc=$?
    set -e
    # App tokens last an hour, which a long wait can outlive: mint a new one,
    # once, before giving up on a 401.
    if [ "$rc" -eq 2 ] && [ "$FETCH_CODE" = "401" ] && [ "$FROM_APP" = "true" ] && [ "$REMINTED" = "false" ] \
        && mint_app_token; then
        echo "sonarqube/github-app: GitHub App token rejected; minted a new one" >&2
        TOKEN="$APP_TOKEN"
        REMINTED=true
        rc=1
    elif [ "$rc" -eq 0 ]; then
        REMINTED=false
    fi
    if [ "$rc" -eq 2 ]; then
        echo "sonarqube/github-app: $FETCH_ERR" >&2
        exit 1
    elif [ "$rc" -eq 1 ]; then
        STATE="$FETCH_ERR"
    else
        SEEN=true
        RESULT="$(jq -c --arg sha "$LUNAR_COMPONENT_GIT_SHA" --arg pr "$LUNAR_COMPONENT_PR" --arg key "$PROJECT_KEY" \
            -f "$HERE/github-app.jq" "$WORK/runs.json")"
        [ "$(printf '%s' "$RESULT" | jq -r '.done')" = "true" ] && break
        STATE="$(printf '%s' "$RESULT" | jq -r '.waiting')"
    fi
    [ "$ELAPSED" -ge "$TIMEOUT" ] && break
    STEP=$((TIMEOUT - ELAPSED < INTERVAL ? TIMEOUT - ELAPSED : INTERVAL))
    sleep "$STEP"
    ELAPSED=$((ELAPSED + STEP))
done

if [ "$(printf '%s' "$RESULT" | jq -r '.done')" = "true" ]; then
    echo "sonarqube/github-app: $(printf '%s' "$RESULT" | jq -r '.summary')" >&2
    printf '%s' "$RESULT" | jq -c '.code_quality' | lunar collect -j ".code_quality" -
    exit 0
fi

if [ "$SEEN" != "true" ]; then
    # No answer from GitHub, so no telling whether SonarQube reported: fail
    # rather than claim it's pending.
    echo "sonarqube/github-app: GitHub didn't answer within ${TIMEOUT}s ($STATE)" >&2
    exit 1
fi
echo "sonarqube/github-app: no completed SonarQube check run for pull request ${LUNAR_COMPONENT_PR} on ${LUNAR_COMPONENT_GIT_SHA} within ${TIMEOUT}s (${STATE}) — writing status=pending" >&2
echo '{"status":"pending"}' | lunar collect -j ".code_quality.native.sonarqube.github_app" -
