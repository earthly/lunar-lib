#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Query DB to check if Semgrep ran on recent PRs
# This provides proof on default branch that scanning is happening

if [ -z "$LUNAR_COMPONENT_ID" ]; then
    echo "LUNAR_COMPONENT_ID is not set, skipping." >&2
    exit 0
fi

if [ -z "$LUNAR_SECRET_PG_PASSWORD" ]; then
    echo "LUNAR_SECRET_PG_PASSWORD is required for the default-branch collector." >&2
    exit 0
fi

# Sanitize component ID to prevent SQL injection (escape single quotes)
SAFE_COMPONENT_ID=$(echo "$LUNAR_COMPONENT_ID" | sed "s/'/''/g")

for CATEGORY in sast sca; do
    QUERY="
        SELECT EXISTS (
            SELECT 1
            FROM components_latest pr
            WHERE pr.component_id = '$SAFE_COMPONENT_ID'
              AND pr.pr IS NOT NULL
              AND jsonb_path_exists(pr.component_json, '$.$CATEGORY.native.semgrep')
        ) AS semgrep_present;
    "
    
    RESULT=$(PGPASSWORD="$LUNAR_SECRET_PG_PASSWORD" \
        psql -t -A -h postgres -U "testuser" -d hub -c "$QUERY" 2>/dev/null || echo "f")
    
    if [ "$RESULT" = "t" ]; then
        jq -n '{github_app_run_recently: true}' | \
            lunar collect -j ".$CATEGORY.native.semgrep" -
        
        write_semgrep_source "$CATEGORY" "github_app"
    fi
done
