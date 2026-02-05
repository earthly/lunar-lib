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
# WHY THIS PATTERN:
# - Avoids requiring separate API tokens for each security tool
# - Works for any tool that only posts PR checks
# - Provides audit trail via Lunar's own data
#
# REUSE: This pattern can be adapted for other tools (Snyk, etc.) by changing
# the jsonb_path_exists query to check for their specific data paths.
# See also: ai-context/strategies.md for documentation of this pattern.
# =============================================================================

if [ -z "$LUNAR_COMPONENT_ID" ]; then
    echo "LUNAR_COMPONENT_ID is not set, skipping." >&2
    exit 0
fi

# Get database connection string from Lunar CLI
# This avoids requiring users to configure PG_PASSWORD separately
CONN_STRING=$(lunar sql connection-string 2>/dev/null || echo "")
if [ -z "$CONN_STRING" ]; then
    echo "Could not get database connection string, skipping." >&2
    exit 0
fi

# Sanitize component ID to prevent SQL injection (escape single quotes)
SAFE_COMPONENT_ID=$(echo "$LUNAR_COMPONENT_ID" | sed "s/'/''/g")

for CATEGORY in sast sca; do
    # Query checks if ANY PR for this component has Semgrep data in the
    # specified category. This proves the GitHub App is configured and running.
    QUERY="
        SELECT EXISTS (
            SELECT 1
            FROM components_latest pr
            WHERE pr.component_id = '$SAFE_COMPONENT_ID'
              AND pr.pr IS NOT NULL
              AND jsonb_path_exists(pr.component_json, '$.$CATEGORY.native.semgrep')
        ) AS semgrep_present;
    "
    
    RESULT=$(psql "$CONN_STRING" -t -A -c "$QUERY" 2>/dev/null || echo "f")
    
    if [ "$RESULT" = "t" ]; then
        jq -n '{github_app_run_recently: true}' | \
            lunar collect -j ".$CATEGORY.native.semgrep" -
        
        write_semgrep_source "$CATEGORY" "github_app"
    fi
done
