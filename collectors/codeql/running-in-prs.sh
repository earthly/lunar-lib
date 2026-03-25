#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

if [ -z "$LUNAR_COMPONENT_ID" ]; then
    exit 0
fi

CONN_STRING=$(lunar sql connection-string 2>/dev/null) || true

if [ -z "$CONN_STRING" ] || [[ "$CONN_STRING" == *"Error"* ]]; then
    exit 0
fi

if ! command -v psql &> /dev/null; then
    apk add --no-cache postgresql-client >/dev/null 2>&1 || exit 0
fi

SAFE_COMPONENT_ID=$(echo "$LUNAR_COMPONENT_ID" | sed "s/'/''/g")

QUERY="
    SELECT EXISTS (
        SELECT 1
        FROM components_latest pr
        WHERE pr.component_id = '$SAFE_COMPONENT_ID'
          AND pr.pr IS NOT NULL
          AND (pr.component_json->'sast'->'native'->'codeql') IS NOT NULL
          AND (pr.component_json->'sast'->'native'->'codeql')::text != 'null'
    ) AS codeql_present;
"

RESULT=$(psql "$CONN_STRING" -t -A -c "$QUERY" 2>/dev/null) || true

if [ "$RESULT" = "t" ]; then
    lunar collect -j ".sast.running_in_prs" "true"
    write_codeql_source "github_app"
fi
