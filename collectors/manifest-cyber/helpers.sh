#!/bin/bash
# Shared helpers for Manifest Cyber collector

MANIFEST_API_BASE="https://api.manifestcyber.com/v1"

# Extract org/repo from LUNAR_COMPONENT_ID (e.g., github.com/acme/api -> acme/api)
get_repo_slug() {
    echo "${LUNAR_COMPONENT_ID#github.com/}"
}

# Make authenticated Manifest API call
# Usage: manifest_api GET /assets
manifest_api() {
    local method="$1"
    local endpoint="$2"
    shift 2
    curl -fsS \
        --connect-timeout 10 \
        --max-time 25 \
        -X "$method" \
        -H "Authorization: Bearer $LUNAR_SECRET_MANIFEST_API_KEY" \
        -H "Content-Type: application/json" \
        "${MANIFEST_API_BASE}${endpoint}" \
        "$@"
}
