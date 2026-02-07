#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# =============================================================================
# DEFAULT BRANCH COMPLIANCE PROOF COLLECTOR
# =============================================================================
#
# PROBLEM: Snyk GitHub App only posts checks on PRs, not on the default branch.
# This creates a compliance gap - we can prove scanning happened on PRs, but
# not on main/master.
#
# SOLUTION: Query the Lunar Hub database to check if this component has Snyk
# data from recent PRs. If PRs are being scanned, we can infer the default
# branch code (which came from merged PRs) was also scanned.
#
# HOW IT WORKS:
# 1. Get DB connection via `lunar sql connection-string`
# 2. Query components_latest for PRs with Snyk data for this component
# 3. If found, write proof to Component JSON that scanning is happening
#
# =============================================================================

if [ -z "$LUNAR_COMPONENT_ID" ]; then
    exit 0
fi

# Get database connection string
CONN_STRING=$(lunar sql connection-string 2>/dev/null) || true

if [ -z "$CONN_STRING" ] || [[ "$CONN_STRING" == *"Error"* ]]; then
    # Fall back to secrets if lunar sql connection-string isn't available
    if [ -n "$LUNAR_SECRET_PG_PASSWORD" ] && [ -n "$LUNAR_HUB_HOST" ]; then
        PG_USER="${LUNAR_SECRET_PG_USER:-api3}"
        CONN_STRING="postgres://${PG_USER}:${LUNAR_SECRET_PG_PASSWORD}@${LUNAR_HUB_HOST}:5432/hub?sslmode=disable"
    else
        # Cannot connect to database - skip silently
        exit 0
    fi
fi

# Check if psql is available
if ! command -v psql &> /dev/null; then
    exit 0
fi

# Sanitize component ID to prevent SQL injection (escape single quotes)
SAFE_COMPONENT_ID=$(echo "$LUNAR_COMPONENT_ID" | sed "s/'/''/g")

for CATEGORY in sca sast container_scan iac_scan; do
    QUERY="
        SELECT EXISTS (
            SELECT 1
            FROM components_latest pr
            WHERE pr.component_id = '$SAFE_COMPONENT_ID'
              AND pr.pr IS NOT NULL
              AND jsonb_path_exists(pr.component_json, '$.$CATEGORY.native.snyk')
        ) AS snyk_present;
    "
    
    RESULT=$(psql "$CONN_STRING" -t -A -c "$QUERY" 2>/dev/null) || true
    
    if [ "$RESULT" = "t" ]; then
        jq -n '{github_app_run_recently: true}' | \
            lunar collect -j ".$CATEGORY.native.snyk" -
        
        write_snyk_source "$CATEGORY" "github_app"
    fi
done
