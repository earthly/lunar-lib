#!/bin/bash

# Shared helper functions for the semgrep collector

# Detect Semgrep product category from check name
detect_semgrep_category() {
    local name="$1"
    local name_lower
    name_lower=$(echo "$name" | tr '[:upper:]' '[:lower:]')
    
    case "$name_lower" in
        *"supply chain"*|*"supply-chain"*|*sca*)
            echo "sca" ;;
        *)
            echo "sast" ;;  # Default: Code analysis
    esac
}

# Detect Semgrep product category from CLI command
detect_semgrep_category_from_cmd() {
    local cmd="$1"
    local cmd_lower
    cmd_lower=$(echo "$cmd" | tr '[:upper:]' '[:lower:]')
    
    if echo "$cmd_lower" | grep -qE "(--supply-chain|supply.chain)"; then
        echo "sca"
    else
        echo "sast"  # Default: Code analysis
    fi
}

# Write source metadata to a category
write_semgrep_source() {
    local category="$1"
    local integration="$2"  # github_app or ci
    local version="${3:-}"  # optional version
    
    if [ -n "$version" ] && [ "$version" != "unknown" ]; then
        jq -n \
            --arg tool "semgrep" \
            --arg integration "$integration" \
            --arg version "$version" \
            '{tool: $tool, integration: $integration, version: $version}' | \
            lunar collect -j ".$category.source" -
    else
        jq -n \
            --arg tool "semgrep" \
            --arg integration "$integration" \
            '{tool: $tool, integration: $integration}' | \
            lunar collect -j ".$category.source" -
    fi
}
