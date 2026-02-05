#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Skip if PG_PASSWORD is not set (optional secret)
if [ -z "$LUNAR_SECRET_PG_PASSWORD" ]; then
    exit 0
fi

# Query DB to check if Snyk ran on recent PRs
# This provides proof on main branch that scanning is happening
for CATEGORY in sca sast container_scan iac_scan; do
    QUERY="
        SELECT EXISTS (
            SELECT 1
            FROM components_latest pr
            WHERE pr.component_id = '$LUNAR_COMPONENT_ID'
              AND pr.pr IS NOT NULL
              AND jsonb_path_exists(pr.component_json, '$.$CATEGORY.native.snyk')
        ) AS snyk_present;
    "
    
    RESULT=$(PGPASSWORD="$LUNAR_SECRET_PG_PASSWORD" \
        psql -t -A -h postgres -U "testuser" -d hub -c "$QUERY" 2>/dev/null || echo "f")
    
    if [ "$RESULT" = "t" ]; then
        jq -n '{github_app_run_recently: true}' | \
            lunar collect -j ".$CATEGORY.native.snyk" -
        
        write_snyk_source "$CATEGORY" "github_app"
    fi
done
