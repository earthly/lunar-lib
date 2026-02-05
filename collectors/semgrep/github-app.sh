#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

if [ -z "$LUNAR_SECRET_GH_TOKEN" ]; then
    echo "LUNAR_SECRET_GH_TOKEN is required for the Semgrep GitHub App collector." >&2
    exit 1
fi

if [ -z "$LUNAR_COMPONENT_GIT_SHA" ]; then
    echo "LUNAR_COMPONENT_GIT_SHA is not set, skipping." >&2
    exit 0
fi

# Extract repo from component ID (strip github.com/ prefix if present)
REPO="${LUNAR_COMPONENT_ID#github.com/}"
if [ -z "$REPO" ]; then
    echo "LUNAR_COMPONENT_ID is not set, skipping." >&2
    exit 0
fi

QUICK_ATTEMPTS=10
LONG_ATTEMPTS=60
SLEEP_SECONDS=2

# API call to GitHub to check for Semgrep in check-runs
fetch_semgrep_checks() {
    curl -fsS \
        -H 'Accept: application/vnd.github+json' \
        -H "Authorization: token $LUNAR_SECRET_GH_TOKEN" \
        "https://api.github.com/repos/$REPO/commits/$LUNAR_COMPONENT_GIT_SHA/check-runs" | \
        jq -c '.check_runs | map(select(.app.slug | test("semgrep";"i")))' 2>/dev/null || echo "[]"
}

FOUND_CHECK=false

# First check for a short while if Semgrep is showing up
for i in $(seq 1 $QUICK_ATTEMPTS); do
    CHECKS=$(fetch_semgrep_checks)
    if [ "$CHECKS" != "[]" ] && [ -n "$CHECKS" ]; then
        FOUND_CHECK=true
        break
    fi
    sleep "$SLEEP_SECONDS"
done

# Exit quickly if no check found
[ "$FOUND_CHECK" = "false" ] && exit 0

# Process each Semgrep check (there may be multiple: Code, Supply Chain)
# Using process substitution to avoid subshell issues with set -e
while read -r CHECK; do
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
    
    # Write native data
    jq -n \
        --argjson results "$RESULT" \
        '{github_app_results: $results}' | \
        lunar collect -j ".$CATEGORY.native.semgrep" -
    
    # Write source metadata
    write_semgrep_source "$CATEGORY" "github_app"
done < <(echo "$CHECKS" | jq -c '.[]')
