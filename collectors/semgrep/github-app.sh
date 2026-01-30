#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

REPO="${LUNAR_COMPONENT_ID#github.com/}"
QUICK_ATTEMPTS=3
LONG_ATTEMPTS=60
SLEEP_SECONDS=2

# API call to GitHub to check for Semgrep in check-runs
fetch_semgrep_checks() {
    curl -fsS \
        -H 'Accept: application/vnd.github+json' \
        -H "Authorization: token $LUNAR_SECRET_GH_TOKEN" \
        "https://api.github.com/repos/$REPO/commits/$LUNAR_COMPONENT_GIT_SHA/check-runs" | \
        jq -c '.check_runs | map(select(.app.slug | test("semgrep";"i")))'
}

FOUND_CHECK=false

# First check for a short while if Semgrep is showing up
for i in $(seq 1 $QUICK_ATTEMPTS); do
    CHECKS=$(fetch_semgrep_checks 2>/dev/null || echo "[]")
    if [ "$CHECKS" != "[]" ] && [ -n "$CHECKS" ]; then
        FOUND_CHECK=true
        break
    fi
    sleep "$SLEEP_SECONDS"
done

# Exit quickly if no check found
[ "$FOUND_CHECK" = "false" ] && exit 0

# Process each Semgrep check (there may be multiple: Code, Supply Chain)
echo "$CHECKS" | jq -c '.[]' | while read -r CHECK; do
    NAME=$(echo "$CHECK" | jq -r '.name // ""')
    STATUS=$(echo "$CHECK" | jq -r '.status // ""')
    
    # Wait for completion if in progress
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
    
    # Detect category and write results
    CATEGORY=$(detect_semgrep_category "$NAME")
    
    # Extract relevant fields
    RESULT=$(echo "$CHECK" | jq -c '{
        id: .id,
        name: .name,
        status: .status,
        conclusion: .conclusion,
        details_url: .details_url,
        html_url: .html_url,
        started_at: .started_at,
        completed_at: .completed_at,
        app_slug: .app.slug
    }')
    
    jq -n \
        --argjson results "$RESULT" \
        '{github_app_results: $results}' | \
        lunar collect -j ".$CATEGORY.native.semgrep" -
    
    jq -n '{tool: "semgrep", integration: "github_app"}' | \
        lunar collect -j ".$CATEGORY.source" -
done
