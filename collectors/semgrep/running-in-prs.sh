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
# 2. Query components_latest2 for PRs with Semgrep data for this component
# 3. If found, write proof to Component JSON that scanning is happening
#
# =============================================================================

if [ -z "$LUNAR_COMPONENT_ID" ]; then
    exit 0
fi

# Get database connection string
CONN_STRING=$(lunar sql connection-string 2>/dev/null) || true

if [ -z "$CONN_STRING" ] || [[ "$CONN_STRING" == *"Error"* ]]; then
    exit 0
fi

# Install psql if not available
if ! command -v psql &> /dev/null; then
    apk add --no-cache postgresql-client >/dev/null 2>&1 || exit 0
fi

# Sanitize component ID to prevent SQL injection (escape single quotes)
SAFE_COMPONENT_ID=$(echo "$LUNAR_COMPONENT_ID" | sed "s/'/''/g")

for CATEGORY in sast sca; do
    # Query components_latest2 for PR data with Semgrep results.
    # Note: using components_latest2 due to temporary schema limitation.
    QUERY="
        SELECT EXISTS (
            SELECT 1
            FROM components_latest2 pr
            WHERE pr.component_id = '$SAFE_COMPONENT_ID'
              AND pr.pr IS NOT NULL
              AND (pr.component_json->'$CATEGORY'->'native'->'semgrep') IS NOT NULL
              AND (pr.component_json->'$CATEGORY'->'native'->'semgrep')::text != 'null'
        ) AS semgrep_present;
    "

    RESULT=$(psql "$CONN_STRING" -t -A -c "$QUERY" 2>/dev/null) || true

    if [ "$RESULT" = "t" ]; then
        # running_in_prs: proves PRs for this component are being scanned
        # (does not imply specific timing, just that scanning capability exists)
        jq -n '{running_in_prs: true}' | \
            lunar collect -j ".$CATEGORY.native.semgrep" -

        write_semgrep_source "$CATEGORY" "github_app"
    fi
done
