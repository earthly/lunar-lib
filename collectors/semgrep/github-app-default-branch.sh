#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# DEBUG: Log start
echo "DEBUG: github-app-default-branch collector starting" >&2
echo "DEBUG: LUNAR_COMPONENT_ID='$LUNAR_COMPONENT_ID'" >&2
echo "DEBUG: LUNAR_HUB_HOST='$LUNAR_HUB_HOST'" >&2
echo "DEBUG: LUNAR_SECRET_PG_PASSWORD set: $([ -n "$LUNAR_SECRET_PG_PASSWORD" ] && echo 'yes' || echo 'no')" >&2

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
    echo "DEBUG: LUNAR_COMPONENT_ID is not set, skipping." >&2
    exit 0
fi

# Get database connection string
# Try lunar sql connection-string first, fall back to environment secrets
echo "DEBUG: Trying lunar sql connection-string..." >&2
CONN_STRING=$(lunar sql connection-string 2>&1) || true
echo "DEBUG: lunar sql connection-string result: '$CONN_STRING'" >&2

if [ -z "$CONN_STRING" ] || [[ "$CONN_STRING" == *"error"* ]] || [[ "$CONN_STRING" == *"Error"* ]]; then
    echo "DEBUG: lunar sql connection-string failed, trying fallback..." >&2
    # Fall back to secrets if lunar sql connection-string isn't available
    if [ -n "$LUNAR_SECRET_PG_PASSWORD" ]; then
        PG_USER="${LUNAR_SECRET_PG_USER:-api3}"
        PG_HOST="${LUNAR_HUB_HOST:-postgres}"
        CONN_STRING="postgres://${PG_USER}:${LUNAR_SECRET_PG_PASSWORD}@${PG_HOST}:5432/hub?sslmode=disable"
        echo "DEBUG: Using fallback connection string with host=$PG_HOST user=$PG_USER" >&2
    else
        echo "DEBUG: No PG_PASSWORD secret available, skipping." >&2
        exit 0
    fi
fi

# Check if psql is available
echo "DEBUG: Checking for psql..." >&2
if ! command -v psql &> /dev/null; then
    echo "DEBUG: psql not found!" >&2
    exit 0
fi
echo "DEBUG: psql found at $(which psql)" >&2

# Sanitize component ID to prevent SQL injection (escape single quotes)
SAFE_COMPONENT_ID=$(echo "$LUNAR_COMPONENT_ID" | sed "s/'/''/g")
echo "DEBUG: SAFE_COMPONENT_ID='$SAFE_COMPONENT_ID'" >&2

for CATEGORY in sast sca; do
    echo "DEBUG: Checking category '$CATEGORY'..." >&2
    
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
    
    echo "DEBUG: Running query for $CATEGORY..." >&2
    RESULT=$(psql "$CONN_STRING" -t -A -c "$QUERY" 2>&1) || true
    echo "DEBUG: Query result for $CATEGORY: '$RESULT'" >&2
    
    if [ "$RESULT" = "t" ]; then
        echo "DEBUG: Found semgrep data for $CATEGORY, writing to component JSON..." >&2
        jq -n '{github_app_run_recently: true}' | \
            lunar collect -j ".$CATEGORY.native.semgrep" -
        
        write_semgrep_source "$CATEGORY" "github_app"
        echo "DEBUG: Wrote $CATEGORY data successfully" >&2
    else
        echo "DEBUG: No semgrep data found for $CATEGORY (result='$RESULT')" >&2
    fi
done

echo "DEBUG: github-app-default-branch collector finished" >&2
