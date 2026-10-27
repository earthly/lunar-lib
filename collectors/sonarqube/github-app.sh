#!/bin/bash
set -e

# Reads the SonarCloud (or SonarQube-for-GitHub) PR check on the current commit
# via the GitHub commit status API. Mirrors collectors/snyk/github-app.sh. Only
# runs on PRs (enforced by runs_on in the manifest). Polls up to
# github_app_poll_timeout_seconds because SonarCloud publishes the status only
# after analysis completes; on timeout writes
# .code_quality.native.sonarqube.github_app.status = "pending".

source "$(dirname "$0")/helpers.sh"

# With github_app set, mint a token from that Hub GitHub App (`lunar github-app add`)
# instead of using the GH_TOKEN secret. The token asks for only the permissions this
# script uses, so an App without them falls back; github_app_only turns that off.
if [ -n "${LUNAR_VAR_GITHUB_APP:-}" ] && APP_TOKEN=$(lunar github-app get-token "$LUNAR_VAR_GITHUB_APP" --permission statuses=read) \
    && [ -n "$APP_TOKEN" ]; then
    echo "GitHub auth: GitHub App $LUNAR_VAR_GITHUB_APP" >&2
    export LUNAR_SECRET_GH_TOKEN="$APP_TOKEN"
elif [ "${LUNAR_VAR_GITHUB_APP_ONLY:-false}" = "true" ]; then
    echo "GitHub auth: no token from GitHub App ${LUNAR_VAR_GITHUB_APP:-(github_app is not set)}, and github_app_only is set" >&2
    exit 1
elif [ -n "${LUNAR_VAR_GITHUB_APP:-}" ]; then
    echo "GitHub auth: GH_TOKEN secret, because GitHub App $LUNAR_VAR_GITHUB_APP minted no token" >&2
fi

if [ -z "${LUNAR_SECRET_GH_TOKEN:-}" ]; then
    echo "sonarqube/github-app: GH_TOKEN secret not set — skipping." >&2
    exit 0
fi

if [ -z "${LUNAR_COMPONENT_GIT_SHA:-}" ]; then
    echo "sonarqube/github-app: no head SHA — skipping." >&2
    exit 0
fi

REPO="${LUNAR_COMPONENT_ID#github.com/}"
TIMEOUT="${LUNAR_VAR_GITHUB_APP_POLL_TIMEOUT_SECONDS:-180}"
INTERVAL="${LUNAR_VAR_GITHUB_APP_POLL_INTERVAL_SECONDS:-10}"

fetch_sonar_statuses() {
    curl -fsS \
        -H "Authorization: token $LUNAR_SECRET_GH_TOKEN" \
        "https://api.github.com/repos/${REPO}/commits/${LUNAR_COMPONENT_GIT_SHA}/status" 2>/dev/null \
        | jq -c '.statuses // [] | map(select(.context|test("sonar";"i")))' \
        2>/dev/null || echo "[]"
}

FOUND="[]"
ELAPSED=0
while [ "$ELAPSED" -lt "$TIMEOUT" ]; do
    STATUSES="$(fetch_sonar_statuses)"
    # A terminal state is success/failure/error. 'pending' means keep polling.
    if [ "$STATUSES" != "[]" ] && [ -n "$STATUSES" ]; then
        HAS_NON_PENDING="$(echo "$STATUSES" | jq '[.[] | select(.state != "pending")] | length')"
        if [ "$HAS_NON_PENDING" -gt 0 ]; then
            FOUND="$STATUSES"
            break
        fi
    fi
    sleep "$INTERVAL"
    ELAPSED=$((ELAPSED + INTERVAL))
done

if [ "$FOUND" = "[]" ]; then
    # Still pending (or never appeared) — emit a pending marker and exit cleanly.
    echo "{\"status\":\"pending\"}" | lunar collect -j ".code_quality.native.sonarqube.github_app" -
    exit 0
fi

# Pick the most relevant status — prefer "Code Analysis" / "SonarCloud" context
# when multiple exist (some repos have both a gate and analysis status).
PICK="$(echo "$FOUND" | jq -c '
  sort_by(if (.context | test("code analysis";"i")) then 0
          elif (.context | test("sonar(cloud|qube)";"i")) then 1
          else 2 end)[0]
')"

STATE="$(echo "$PICK" | jq -r '.state // ""')"
CONTEXT="$(echo "$PICK" | jq -r '.context // ""')"
TARGET_URL="$(echo "$PICK" | jq -r '.target_url // ""')"

jq -n \
    --arg status "complete" \
    --arg state "$STATE" \
    --arg context "$CONTEXT" \
    --arg target_url "$TARGET_URL" \
    '{status: $status, state: $state, context: $context, target_url: $target_url}' \
    | lunar collect -j ".code_quality.native.sonarqube.github_app" -

# Source metadata — record that sonarqube data was observed via the GitHub App.
PROJECT_KEY="$(sq_project_key)"
BASE_URL="$(sq_base_url)"
jq -n \
    --arg tool "sonarqube" \
    --arg integration "github_app" \
    --arg key "${PROJECT_KEY}" \
    --arg url "$BASE_URL" \
    '{tool: $tool, integration: $integration, project_key: $key, api_url: $url}' \
    | lunar collect -j ".code_quality.source" -
