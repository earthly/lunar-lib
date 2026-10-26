#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# With github_app set, mint a token from that Hub GitHub App (`lunar github-app add`)
# instead of using the GH_TOKEN secret; github_app_only turns the fallback off.
if [ -n "${LUNAR_VAR_GITHUB_APP:-}" ] && APP_TOKEN=$(lunar github-app get-token "$LUNAR_VAR_GITHUB_APP" 2>/dev/null) && [ -n "$APP_TOKEN" ]; then
    echo "GitHub auth: GitHub App $LUNAR_VAR_GITHUB_APP" >&2
    export LUNAR_SECRET_GH_TOKEN="$APP_TOKEN"
elif [ "${LUNAR_VAR_GITHUB_APP_ONLY:-false}" = "true" ]; then
    echo "GitHub auth: no token from GitHub App ${LUNAR_VAR_GITHUB_APP:-(github_app is not set)}, and github_app_only is set" >&2
    exit 1
elif [ -n "${LUNAR_VAR_GITHUB_APP:-}" ]; then
    echo "GitHub auth: GH_TOKEN secret, because GitHub App $LUNAR_VAR_GITHUB_APP minted no token" >&2
fi

if [ -z "$LUNAR_SECRET_GH_TOKEN" ]; then
    echo "LUNAR_SECRET_GH_TOKEN is required for the Snyk GitHub App collector." >&2
    exit 1
fi

REPO="${LUNAR_COMPONENT_ID#github.com/}"
QUICK_ATTEMPTS=10
LONG_ATTEMPTS=60
SLEEP_SECONDS=2

# API call to GitHub to check for Snyk in commit statuses
fetch_snyk_statuses() {
    curl -fsS \
        -H "Authorization: token $LUNAR_SECRET_GH_TOKEN" \
        "https://api.github.com/repos/$REPO/commits/$LUNAR_COMPONENT_GIT_SHA/status" | \
        jq -c '.statuses | map(select(.context|test("snyk";"i")))' 2>/dev/null || echo "[]"
}

FOUND_CHECK=false

# First check for a short while if Snyk is showing up
for i in $(seq 1 $QUICK_ATTEMPTS); do
    STATUSES=$(fetch_snyk_statuses)
    if [ "$STATUSES" != "[]" ] && [ -n "$STATUSES" ]; then
        FOUND_CHECK=true
        break
    fi
    sleep "$SLEEP_SECONDS"
done

# Exit quickly if no check found
[ "$FOUND_CHECK" = "false" ] && exit 0

# Process each Snyk status (there may be multiple: Open Source, Code, etc.)
echo "$STATUSES" | jq -c '.[]' | while read -r STATUS; do
    CONTEXT=$(echo "$STATUS" | jq -r '.context // ""')
    STATE=$(echo "$STATUS" | jq -r '.state // ""')
    
    # Wait for completion if pending
    if [ "$STATE" = "pending" ]; then
        for j in $(seq 1 $LONG_ATTEMPTS); do
            sleep "$SLEEP_SECONDS"
            STATUS=$(curl -fsS \
                -H "Authorization: token $LUNAR_SECRET_GH_TOKEN" \
                "https://api.github.com/repos/$REPO/commits/$LUNAR_COMPONENT_GIT_SHA/status" | \
                jq -c --arg ctx "$CONTEXT" '.statuses | map(select(.context == $ctx)) | first' 2>/dev/null || echo "null")
            STATE=$(echo "$STATUS" | jq -r '.state // ""')
            [ "$STATE" != "pending" ] && break
        done
    fi
    
    # Detect category and write results
    CATEGORY=$(detect_snyk_category "$CONTEXT")
    
    # Write native data
    jq -n \
        --argjson results "$STATUS" \
        '{github_app: $results}' | \
        lunar collect -j ".$CATEGORY.native.snyk" -
    
    # Write source metadata
    write_snyk_source "$CATEGORY" "github_app"
done
