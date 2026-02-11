#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# =============================================================================
# DEFAULT BRANCH COMPLIANCE PROOF COLLECTOR
# =============================================================================
#
# PROBLEM: Many security tools (Semgrep, Snyk, etc.) only post GitHub checks on
# PRs, not on the default branch. This creates a compliance gap - we can prove
# scanning happened on PRs, but not on main/master.
#
# SOLUTION: Query the Lunar Hub database to check if this component has Semgrep
# data from recent PRs. If PRs are being scanned, we can infer the default
# branch code (which came from merged PRs) was also scanned.
#
# HOW IT WORKS:
# 1. Get DB connection via `lunar sql connection-string`
# 2. Query components_latest for PRs with Semgrep data for this component
# 3. If found, write proof to Component JSON that scanning is happening
#
# KNOWN LIMITATION: Currently requires LUNAR_HUB_HOST to be passed to collectors
# for database connectivity. This is a platform feature that needs to be enabled.
#
# =============================================================================

if [ -z "$LUNAR_COMPONENT_ID" ]; then
    exit 0
fi

# Get database connection string.
# Priority: explicit secret > lunar sql > constructed from env vars.
# NOTE: Code collectors run in Docker containers on the default bridge network.
# They cannot resolve Docker Compose hostnames (hub, postgres). The connection
# string returned by `lunar sql connection-string` or constructed from
# LUNAR_HUB_HOST may use internal hostnames. Pass PG_CONNECTION_STRING as a
# secret with a host-reachable address to work around this.
if [ -n "$LUNAR_SECRET_PG_CONNECTION_STRING" ]; then
    CONN_STRING="$LUNAR_SECRET_PG_CONNECTION_STRING"
else
    CONN_STRING=$(lunar sql connection-string 2>/dev/null) || true
    if [ -z "$CONN_STRING" ] || [[ "$CONN_STRING" == *"Error"* ]]; then
        if [ -n "$LUNAR_SECRET_PG_PASSWORD" ] && [ -n "$LUNAR_HUB_HOST" ]; then
            PG_USER="${LUNAR_SECRET_PG_USER:-api3}"
            CONN_STRING="postgres://${PG_USER}:${LUNAR_SECRET_PG_PASSWORD}@${LUNAR_HUB_HOST}:5432/hub?sslmode=disable"
        else
            # Cannot connect to database - skip silently
            exit 0
        fi
    fi
fi

# TEMP TEST: Override with hardcoded connection string via Docker bridge gateway.
# Collector containers are on the default bridge network and can reach the host
# at 172.17.0.1 where postgres port 5432 is published.
# TODO: Remove this once HUB_COLLECTOR_SECRETS or Docker networking is fixed.
CONN_STRING="postgres://api3:secret@172.17.0.1:5432/hub?sslmode=disable"

# Check if psql is available
if ! command -v psql &> /dev/null; then
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
    
    RESULT=$(psql "$CONN_STRING" -t -A -c "$QUERY" 2>/dev/null) || true
    
    if [ "$RESULT" = "t" ]; then
        # pr_scanning_verified: proves PRs for this component are being scanned
        # (does not imply specific timing, just that scanning capability exists)
        jq -n '{pr_scanning_verified: true}' | \
            lunar collect -j ".$CATEGORY.native.semgrep" -
        
        write_semgrep_source "$CATEGORY" "github_app"
    fi
done
