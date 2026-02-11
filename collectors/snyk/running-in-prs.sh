#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# =============================================================================
# DEFAULT BRANCH COMPLIANCE PROOF COLLECTOR
# =============================================================================

if [ -z "$LUNAR_COMPONENT_ID" ]; then
    exit 0
fi

# Get database connection string.
# Priority: explicit secret > lunar sql > constructed from env vars.
# NOTE: Code collectors run in Docker containers on the default bridge network.
# They cannot resolve Docker Compose hostnames (hub, postgres). Pass
# PG_CONNECTION_STRING as a secret with a host-reachable address to work around.
if [ -n "$LUNAR_SECRET_PG_CONNECTION_STRING" ]; then
    CONN_STRING="$LUNAR_SECRET_PG_CONNECTION_STRING"
else
    CONN_STRING=$(lunar sql connection-string 2>/dev/null) || true
    if [ -z "$CONN_STRING" ] || [[ "$CONN_STRING" == *"Error"* ]]; then
        if [ -n "$LUNAR_SECRET_PG_PASSWORD" ] && [ -n "$LUNAR_HUB_HOST" ]; then
            PG_USER="${LUNAR_SECRET_PG_USER:-api3}"
            CONN_STRING="postgres://${PG_USER}:${LUNAR_SECRET_PG_PASSWORD}@${LUNAR_HUB_HOST}:5432/hub?sslmode=disable"
        else
            exit 0
        fi
    fi
fi

# Install psql if not available (base image may have a cached version without it)
if ! command -v psql &> /dev/null; then
    apk add --no-cache postgresql-client >/dev/null 2>&1 || exit 0
    command -v psql &> /dev/null || exit 0
fi

# Quick connectivity check — bail fast if we can't reach the DB
if ! timeout 10 psql "$CONN_STRING" -c "SELECT 1" >/dev/null 2>&1; then
    exit 0
fi

# Sanitize component ID to prevent SQL injection (escape single quotes)
SAFE_COMPONENT_ID=$(echo "$LUNAR_COMPONENT_ID" | sed "s/'/''/g")

for CATEGORY in sca sast container_scan iac_scan; do
    # Query components_latest2 for PR data with Snyk results.
    # Note: using components_latest2 due to temporary schema limitation.
    QUERY="SELECT EXISTS (SELECT 1 FROM components_latest2 pr WHERE pr.component_id = '$SAFE_COMPONENT_ID' AND pr.pr IS NOT NULL AND (pr.component_json->'$CATEGORY'->'native'->'snyk') IS NOT NULL AND (pr.component_json->'$CATEGORY'->'native'->'snyk')::text != 'null') AS snyk_present;"

    RESULT=$(timeout 15 psql "$CONN_STRING" -t -A -c "$QUERY" 2>/dev/null) || true

    if [ "$RESULT" = "t" ]; then
        # pr_scanning_verified: proves PRs for this component are being scanned
        jq -n '{pr_scanning_verified: true}' | lunar collect -j ".$CATEGORY.native.snyk" -
        write_snyk_source "$CATEGORY" "github_app"
    fi
done
