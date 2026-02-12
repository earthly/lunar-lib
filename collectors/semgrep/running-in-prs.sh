#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

if [ -z "$LUNAR_COMPONENT_ID" ]; then
    exit 0
fi

echo "DEBUG: LUNAR_HUB_HOST=$LUNAR_HUB_HOST" >&2
echo "DEBUG: LUNAR_HUB_GRPC_PORT=$LUNAR_HUB_GRPC_PORT" >&2
echo "DEBUG: LUNAR_HUB_INSECURE=$LUNAR_HUB_INSECURE" >&2

# Try lunar sql connection-string
echo "DEBUG: running lunar sql connection-string..." >&2
CONN_RAW=$(lunar sql connection-string 2>&1) || true
echo "DEBUG: raw output='$CONN_RAW'" >&2

if [ -n "$LUNAR_SECRET_PG_CONNECTION_STRING" ]; then
    CONN_STRING="$LUNAR_SECRET_PG_CONNECTION_STRING"
    echo "DEBUG: using PG_CONNECTION_STRING secret" >&2
elif [ -n "$CONN_RAW" ] && [[ "$CONN_RAW" != *"Error"* ]] && [[ "$CONN_RAW" != *"error"* ]]; then
    CONN_STRING="$CONN_RAW"
    echo "DEBUG: using lunar sql connection-string" >&2
elif [ -n "$LUNAR_SECRET_PG_PASSWORD" ] && [ -n "$LUNAR_HUB_HOST" ]; then
    PG_USER="${LUNAR_SECRET_PG_USER:-api3}"
    CONN_STRING="postgres://${PG_USER}:${LUNAR_SECRET_PG_PASSWORD}@${LUNAR_HUB_HOST}:5432/hub?sslmode=disable"
    echo "DEBUG: using constructed connection string" >&2
else
    echo "DEBUG: no connection method available, exiting" >&2
    exit 0
fi

echo "DEBUG: CONN_STRING host=$(echo "$CONN_STRING" | sed 's|.*@\([^/:]*\).*|\1|')" >&2

# Install psql if not available
if ! command -v psql &> /dev/null; then
    echo "DEBUG: installing psql..." >&2
    apk add --no-cache postgresql-client >/dev/null 2>&1 || { echo "DEBUG: apk add failed" >&2; exit 0; }
    command -v psql &> /dev/null || { echo "DEBUG: psql still not found" >&2; exit 0; }
    echo "DEBUG: psql installed" >&2
else
    echo "DEBUG: psql already available" >&2
fi

# Connectivity check
echo "DEBUG: testing connectivity..." >&2
CONN_TEST=$(timeout 10 psql "$CONN_STRING" -c "SELECT 1" 2>&1) || true
echo "DEBUG: connectivity result='$CONN_TEST'" >&2
if ! echo "$CONN_TEST" | grep -q "1"; then
    echo "DEBUG: cannot reach DB, exiting" >&2
    exit 0
fi
echo "DEBUG: DB OK" >&2

SAFE_COMPONENT_ID=$(echo "$LUNAR_COMPONENT_ID" | sed "s/'/''/g")
echo "DEBUG: component=$SAFE_COMPONENT_ID" >&2

for CATEGORY in sast sca; do
    QUERY="SELECT EXISTS (SELECT 1 FROM components_latest2 pr WHERE pr.component_id = '$SAFE_COMPONENT_ID' AND pr.pr IS NOT NULL AND (pr.component_json->'$CATEGORY'->'native'->'semgrep') IS NOT NULL AND (pr.component_json->'$CATEGORY'->'native'->'semgrep')::text != 'null') AS semgrep_present;"

    echo "DEBUG: querying $CATEGORY..." >&2
    RESULT=$(timeout 15 psql "$CONN_STRING" -t -A -c "$QUERY" 2>&1) || true
    echo "DEBUG: $CATEGORY result='$RESULT'" >&2

    if [ "$RESULT" = "t" ]; then
        echo "DEBUG: collecting $CATEGORY" >&2
        jq -n '{pr_scanning_verified: true}' | lunar collect -j ".$CATEGORY.native.semgrep" -
        write_semgrep_source "$CATEGORY" "github_app"
    fi
done
echo "DEBUG: done" >&2
