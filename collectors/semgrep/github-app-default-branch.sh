#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Query DB to check if Semgrep ran on recent PRs
# This provides proof on main branch that scanning is happening

for CATEGORY in sast sca; do
    QUERY="
        SELECT EXISTS (
            SELECT 1
            FROM components_latest pr
            WHERE pr.component_id = '$LUNAR_COMPONENT_ID'
              AND pr.pr IS NOT NULL
              AND jsonb_path_exists(pr.component_json, '$.$CATEGORY.native.semgrep')
        ) AS semgrep_present;
    "
    
    RESULT=$(PGPASSWORD="$LUNAR_SECRET_PG_PASSWORD" \
        psql -t -A -h postgres -U "testuser" -d hub -c "$QUERY" 2>/dev/null || echo "f")
    
    if [ "$RESULT" = "t" ]; then
        jq -n '{github_app_run_recently: true}' | \
            lunar collect -j ".$CATEGORY.native.semgrep" -
        
        jq -n '{tool: "semgrep", integration: "github_app"}' | \
            lunar collect -j ".$CATEGORY.source" -
    fi
done
