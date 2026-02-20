#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

if [ -z "$LUNAR_SECRET_GH_TOKEN" ]; then
    echo "LUNAR_SECRET_GH_TOKEN is required for the Manifest Cyber GitHub App collector." >&2
    exit 1
fi

REPO=$(get_repo_slug)
QUICK_ATTEMPTS=10
LONG_ATTEMPTS=60
SLEEP_SECONDS=2

# Check GitHub commit statuses for Manifest Cyber
fetch_manifest_statuses() {
    curl -fsS \
        -H "Authorization: token $LUNAR_SECRET_GH_TOKEN" \
        "https://api.github.com/repos/$REPO/commits/$LUNAR_COMPONENT_GIT_SHA/status" | \
        jq -c '.statuses | map(select(.context | test("manifest";"i")))' 2>/dev/null || echo "[]"
}

# Also check GitHub check runs (Manifest may use Checks API instead of Statuses)
fetch_manifest_checks() {
    curl -fsS \
        -H "Authorization: token $LUNAR_SECRET_GH_TOKEN" \
        -H "Accept: application/vnd.github+json" \
        "https://api.github.com/repos/$REPO/commits/$LUNAR_COMPONENT_GIT_SHA/check-runs" | \
        jq -c '.check_runs | map(select(.name | test("manifest";"i")))' 2>/dev/null || echo "[]"
}

FOUND_CHECK=false

# Poll for Manifest status checks
for i in $(seq 1 $QUICK_ATTEMPTS); do
    STATUSES=$(fetch_manifest_statuses)
    CHECKS=$(fetch_manifest_checks)

    if { [ "$STATUSES" != "[]" ] && [ -n "$STATUSES" ]; } || \
       { [ "$CHECKS" != "[]" ] && [ -n "$CHECKS" ]; }; then
        FOUND_CHECK=true
        break
    fi
    sleep "$SLEEP_SECONDS"
done

# Exit quietly if no Manifest checks found
[ "$FOUND_CHECK" = "false" ] && exit 0

# Process commit statuses (Status API)
if [ "$STATUSES" != "[]" ] && [ -n "$STATUSES" ]; then
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

        # Write GitHub App status data
        jq -n --argjson results "$STATUS" '{github_app: $results}' | \
            lunar collect -j ".sbom.native.manifest" -

        write_source ".sbom" "github_app"
    done
fi

# Process check runs (Checks API)
if [ "$CHECKS" != "[]" ] && [ -n "$CHECKS" ]; then
    echo "$CHECKS" | jq -c '.[]' | while read -r CHECK; do
        NAME=$(echo "$CHECK" | jq -r '.name // ""')
        STATUS=$(echo "$CHECK" | jq -r '.status // ""')
        CONCLUSION=$(echo "$CHECK" | jq -r '.conclusion // ""')

        # Wait for completion if in progress
        if [ "$STATUS" = "in_progress" ] || [ "$STATUS" = "queued" ]; then
            for j in $(seq 1 $LONG_ATTEMPTS); do
                sleep "$SLEEP_SECONDS"
                CHECK=$(curl -fsS \
                    -H "Authorization: token $LUNAR_SECRET_GH_TOKEN" \
                    -H "Accept: application/vnd.github+json" \
                    "https://api.github.com/repos/$REPO/commits/$LUNAR_COMPONENT_GIT_SHA/check-runs" | \
                    jq -c --arg name "$NAME" '.check_runs | map(select(.name == $name)) | first' 2>/dev/null || echo "null")
                STATUS=$(echo "$CHECK" | jq -r '.status // ""')
                [ "$STATUS" = "completed" ] && break
            done
            CONCLUSION=$(echo "$CHECK" | jq -r '.conclusion // ""')
        fi

        # Write check run data
        jq -n \
            --arg name "$NAME" \
            --arg status "$STATUS" \
            --arg conclusion "$CONCLUSION" \
            --arg url "$(echo "$CHECK" | jq -r '.html_url // ""')" \
            '{github_app: {name: $name, status: $status, conclusion: $conclusion, url: $url}}' | \
            lunar collect -j ".sbom.native.manifest" -

        write_source ".sbom" "github_app"
    done
fi
