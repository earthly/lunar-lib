#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

if ! is_ruby_project; then
    exit 0
fi

[[ -f "Gemfile.lock" ]] || { echo "No Gemfile.lock found, skipping bundler-audit" >&2; exit 0; }

if ! command -v bundle >/dev/null 2>&1; then
    echo "bundle not available, skipping bundler-audit" >&2
    exit 0
fi

# Try to update the advisory database (may fail in network-isolated containers).
# The Docker image ships with a pre-baked copy of ruby-advisory-db as fallback.
bundle audit update 2>/dev/null || echo "Using pre-baked advisory DB" >&2

# Run audit — non-zero exit means vulnerabilities found
set +e
audit_output=$(bundle audit check 2>&1)
audit_exit=$?
set -e

# Parse vulnerability blocks from text output
# Format: Name: / Version: / Advisory: or CVE: / Criticality: / Title: / blank line
vulns_json="[]"
gem_name="" gem_ver="" advisory="" title="" crit=""

while IFS= read -r line; do
    case "$line" in
        Name:*)        gem_name=$(echo "$line" | sed 's/^Name:[[:space:]]*//') ;;
        Version:*)     gem_ver=$(echo "$line" | sed 's/^Version:[[:space:]]*//') ;;
        Advisory:*|CVE:*|GHSA:*)
                       advisory=$(echo "$line" | sed 's/^[A-Za-z]*:[[:space:]]*//') ;;
        Criticality:*) crit=$(echo "$line" | sed 's/^Criticality:[[:space:]]*//') ;;
        Title:*)       title=$(echo "$line" | sed 's/^Title:[[:space:]]*//') ;;
        "")
            if [[ -n "$gem_name" ]]; then
                entry=$(jq -n \
                    --arg gem "$gem_name" \
                    --arg version "$gem_ver" \
                    --arg advisory "$advisory" \
                    --arg title "$title" \
                    --arg criticality "$crit" \
                    '{gem: $gem, version: $version, advisory: $advisory, title: $title, criticality: $criticality}')
                vulns_json=$(echo "$vulns_json" | jq --argjson e "$entry" '. + [$e]')
                gem_name="" gem_ver="" advisory="" title="" crit=""
            fi
            ;;
    esac
done <<< "$audit_output"

# Catch last block if no trailing blank line
if [[ -n "$gem_name" ]]; then
    entry=$(jq -n \
        --arg gem "$gem_name" \
        --arg version "$gem_ver" \
        --arg advisory "$advisory" \
        --arg title "$title" \
        --arg criticality "$crit" \
        '{gem: $gem, version: $version, advisory: $advisory, title: $title, criticality: $criticality}')
    vulns_json=$(echo "$vulns_json" | jq --argjson e "$entry" '. + [$e]')
fi

jq -n \
    --argjson vulnerabilities "$vulns_json" \
    '{
        vulnerabilities: $vulnerabilities,
        source: { tool: "bundler-audit", integration: "code" }
    }' | lunar collect -j ".lang.ruby.bundler_audit" -
