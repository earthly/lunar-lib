#!/bin/bash
set -e

# Detect CodeRabbit check-runs on pull requests.
# Queries GitHub check-runs API and writes to ai.code_reviewers[].

# With github_app set, mint a token from that Hub GitHub App (`lunar github-app add`)
# instead of using the GH_TOKEN secret. The token asks for only the permissions this
# script uses, so an App without them falls back; github_app_only turns that off.
if [ -n "${LUNAR_VAR_GITHUB_APP:-}" ] && APP_TOKEN=$(lunar github-app get-token "$LUNAR_VAR_GITHUB_APP" --permission checks=read) \
    && [ -n "$APP_TOKEN" ]; then
  echo "GitHub auth: GitHub App $LUNAR_VAR_GITHUB_APP" >&2
  export LUNAR_SECRET_GH_TOKEN="$APP_TOKEN"
elif [ "${LUNAR_VAR_GITHUB_APP_ONLY:-false}" = "true" ]; then
  echo "GitHub auth: no token from GitHub App ${LUNAR_VAR_GITHUB_APP:-(github_app is not set)}, and github_app_only is set" >&2
  exit 1
elif [ -n "${LUNAR_VAR_GITHUB_APP:-}" ]; then
  echo "GitHub auth: GH_TOKEN secret, because GitHub App $LUNAR_VAR_GITHUB_APP minted no token" >&2
fi

if [ -z "$LUNAR_SECRET_GH_TOKEN" ]; then
  echo "LUNAR_SECRET_GH_TOKEN is required for CodeRabbit code-reviewer detection." >&2
  exit 1
fi

REPO="${LUNAR_COMPONENT_ID#github.com/}"
QUICK_ATTEMPTS=10
LONG_ATTEMPTS=60
SLEEP_SECONDS=2

fetch_coderabbit_checks() {
  curl -fsS \
    -H 'Accept: application/vnd.github+json' \
    -H "Authorization: token $LUNAR_SECRET_GH_TOKEN" \
    "https://api.github.com/repos/$REPO/commits/$LUNAR_COMPONENT_GIT_SHA/check-runs" | \
    jq -c '.check_runs | map(select(.app.slug == "coderabbitai"))' 2>/dev/null || echo "[]"
}

FOUND_CHECK=false
for i in $(seq 1 $QUICK_ATTEMPTS); do
  CHECKS=$(fetch_coderabbit_checks)
  if [ "$CHECKS" != "[]" ] && [ -n "$CHECKS" ]; then
    FOUND_CHECK=true
    break
  fi
  sleep "$SLEEP_SECONDS"
done

[ "$FOUND_CHECK" = "false" ] && exit 0

while read -r CHECK; do
  STATUS=$(echo "$CHECK" | jq -r '.status // ""')

  if [ "$STATUS" = "in_progress" ] || [ "$STATUS" = "queued" ]; then
    CHECK_ID=$(echo "$CHECK" | jq -r '.id')
    for j in $(seq 1 $LONG_ATTEMPTS); do
      sleep "$SLEEP_SECONDS"
      CHECK=$(curl -fsS \
        -H 'Accept: application/vnd.github+json' \
        -H "Authorization: token $LUNAR_SECRET_GH_TOKEN" \
        "https://api.github.com/repos/$REPO/check-runs/$CHECK_ID" 2>/dev/null || echo "{}")
      STATUS=$(echo "$CHECK" | jq -r '.status // ""')
      [ "$STATUS" = "completed" ] && break
    done
  fi

  COMPLETED_AT=$(echo "$CHECK" | jq -r '.completed_at // .started_at // empty')
  CHECK_NAME=$(echo "$CHECK" | jq -r '.name // "coderabbitai"')

  jq -n \
    --arg tool "coderabbit" \
    --arg check_name "$CHECK_NAME" \
    --argjson detected true \
    --arg last_seen "$COMPLETED_AT" \
    '{
      tool: $tool,
      check_name: $check_name,
      detected: $detected,
      last_seen: $last_seen
    }' | lunar collect -j ".ai.code_reviewers[]" -

done < <(echo "$CHECKS" | jq -c '.[]')
