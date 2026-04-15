#!/bin/bash
set -e

# Detect Claude Code Review check-runs on pull requests.
# Queries GitHub check-runs API and writes to ai.code_reviewers[].

if [ -z "$LUNAR_SECRET_GH_TOKEN" ]; then
  echo "LUNAR_SECRET_GH_TOKEN is required for Claude code-reviewer detection." >&2
  exit 1
fi

REPO="${LUNAR_COMPONENT_ID#github.com/}"
QUICK_ATTEMPTS=10
LONG_ATTEMPTS=60
SLEEP_SECONDS=2

fetch_claude_checks() {
  curl -fsS \
    -H 'Accept: application/vnd.github+json' \
    -H "Authorization: token $LUNAR_SECRET_GH_TOKEN" \
    "https://api.github.com/repos/$REPO/commits/$LUNAR_COMPONENT_GIT_SHA/check-runs" | \
    jq -c '.check_runs | map(select(.app.slug == "claude-ai" or .app.slug == "claude" or (.name | test("claude.*review"; "i"))))' 2>/dev/null || echo "[]"
}

# Wait for check to appear
FOUND_CHECK=false
for i in $(seq 1 $QUICK_ATTEMPTS); do
  CHECKS=$(fetch_claude_checks)
  if [ "$CHECKS" != "[]" ] && [ -n "$CHECKS" ]; then
    FOUND_CHECK=true
    break
  fi
  sleep "$SLEEP_SECONDS"
done

# No Claude review detected — exit silently
[ "$FOUND_CHECK" = "false" ] && exit 0

# Wait for completion and write results
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
  CHECK_NAME=$(echo "$CHECK" | jq -r '.name // "Claude Code Review"')

  # Write to normalized ai.code_reviewers[]
  jq -n \
    --arg tool "claude" \
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
