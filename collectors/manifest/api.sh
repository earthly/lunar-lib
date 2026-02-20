#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

if [ -z "$LUNAR_SECRET_MANIFEST_API_KEY" ]; then
    echo "LUNAR_SECRET_MANIFEST_API_KEY is required for the Manifest Cyber API collector." >&2
    exit 1
fi

REPO_SLUG=$(get_repo_slug)

# ------------------------------------------------------------------
# Find the asset in Manifest Cyber matching this component
# The API endpoint and matching logic may need adjustment once we have
# a real account to test against. Manifest may key assets by repo URL,
# product name, or an internal ID.
# ------------------------------------------------------------------

# Try to find the asset by repository name
ASSET=$(manifest_api GET "/assets?search=${REPO_SLUG}" 2>/dev/null || echo "")

if [ -z "$ASSET" ] || [ "$ASSET" = "null" ] || [ "$ASSET" = "[]" ]; then
    echo "No Manifest Cyber asset found for ${REPO_SLUG}, skipping." >&2
    exit 0
fi

# Extract the first matching asset
# NOTE: The actual response structure may differ — adjust jq paths
# after testing with a real Manifest account
ASSET_DATA=$(echo "$ASSET" | jq -c '
    if type == "array" then .[0]
    elif .data? then .data[0]
    else .
    end // empty
' 2>/dev/null || echo "")

if [ -z "$ASSET_DATA" ]; then
    echo "Could not parse Manifest asset data for ${REPO_SLUG}, skipping." >&2
    exit 0
fi

# ------------------------------------------------------------------
# Extract SBOM summary data
# ------------------------------------------------------------------

ASSET_ID=$(echo "$ASSET_DATA" | jq -r '.id // .asset_id // ""')
ASSET_NAME=$(echo "$ASSET_DATA" | jq -r '.name // .asset_name // ""')
PACKAGE_COUNT=$(echo "$ASSET_DATA" | jq -r '.component_count // .package_count // 0')
SBOM_FORMAT=$(echo "$ASSET_DATA" | jq -r '.sbom_format // .format // "unknown"')
LAST_UPDATED=$(echo "$ASSET_DATA" | jq -r '.updated_at // .last_updated // ""')

# Write source metadata
write_source ".sbom" "api"

# Write normalized SBOM summary
jq -n \
    --argjson packages "$PACKAGE_COUNT" \
    --arg last_updated "$LAST_UPDATED" \
    '{packages: $packages, last_updated: $last_updated}' | \
    lunar collect -j ".sbom.summary" -

# ------------------------------------------------------------------
# Fetch vulnerability enrichment data
# ------------------------------------------------------------------

VULN_DATA=$(manifest_api GET "/assets/${ASSET_ID}/vulnerabilities" 2>/dev/null || echo "")

if [ -n "$VULN_DATA" ] && [ "$VULN_DATA" != "null" ]; then
    # Extract vulnerability counts by severity
    # NOTE: Adjust jq paths based on actual API response structure
    VULN_SUMMARY=$(echo "$VULN_DATA" | jq -c '
        {
            critical: ([.[] | select(.severity == "critical" or .severity == "CRITICAL")] | length),
            high: ([.[] | select(.severity == "high" or .severity == "HIGH")] | length),
            medium: ([.[] | select(.severity == "medium" or .severity == "MEDIUM")] | length),
            low: ([.[] | select(.severity == "low" or .severity == "LOW")] | length)
        } | . + {total: (.critical + .high + .medium + .low)}
    ' 2>/dev/null || echo '{"critical":0,"high":0,"medium":0,"low":0,"total":0}')

    # Write normalized SCA vulnerability counts
    write_source ".sca" "api"
    echo "$VULN_SUMMARY" | lunar collect -j ".sca.vulnerabilities" -

    # Count CISA KEV and high-EPSS vulns for exploitability data
    KEV_COUNT=$(echo "$VULN_DATA" | jq '[.[] | select(.kev == true or .in_kev == true)] | length' 2>/dev/null || echo 0)
    EPSS_HIGH=$(echo "$VULN_DATA" | jq '[.[] | select((.epss_score // 0) > 0.5)] | length' 2>/dev/null || echo 0)

    # Write native Manifest data (vulns + exploitability)
    jq -n \
        --arg asset_id "$ASSET_ID" \
        --arg asset_name "$ASSET_NAME" \
        --argjson vulns "$VULN_SUMMARY" \
        --argjson kev "$KEV_COUNT" \
        --argjson epss_high "$EPSS_HIGH" \
        --arg sbom_format "$SBOM_FORMAT" \
        '{
            asset_id: $asset_id,
            asset_name: $asset_name,
            vulnerabilities: $vulns,
            exploitability: {kev_count: $kev, epss_high_count: $epss_high},
            sbom_format: $sbom_format
        }' | lunar collect -j ".sbom.native.manifest" -
else
    # No vulnerability data — still write asset metadata
    jq -n \
        --arg asset_id "$ASSET_ID" \
        --arg asset_name "$ASSET_NAME" \
        --arg sbom_format "$SBOM_FORMAT" \
        '{asset_id: $asset_id, asset_name: $asset_name, sbom_format: $sbom_format}' | \
        lunar collect -j ".sbom.native.manifest" -
fi

# ------------------------------------------------------------------
# Fetch license data
# ------------------------------------------------------------------

LICENSE_DATA=$(manifest_api GET "/assets/${ASSET_ID}/licenses" 2>/dev/null || echo "")

if [ -n "$LICENSE_DATA" ] && [ "$LICENSE_DATA" != "null" ]; then
    # Extract unique license IDs for the normalized summary
    LICENSES=$(echo "$LICENSE_DATA" | jq -c '[.[].id // .[].license_id // .[].name] | unique' 2>/dev/null || echo '[]')
    echo "$LICENSES" | jq -c '{licenses: .}' | lunar collect -j ".sbom.summary" -

    # Write detailed license breakdown to native data
    LICENSE_BREAKDOWN=$(echo "$LICENSE_DATA" | jq -c '[.[] | {id: (.id // .license_id // .name), package_count: (.count // .package_count // 1)}]' 2>/dev/null || echo '[]')
    echo "$LICENSE_BREAKDOWN" | jq -c '{licenses: .}' | lunar collect -j ".sbom.native.manifest" -
fi
