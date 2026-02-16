#!/bin/bash

# Shared helper functions for the snyk collector

# Detect Snyk product category from check context/name
detect_snyk_category() {
    local context="$1"
    local context_lower
    context_lower=$(echo "$context" | tr '[:upper:]' '[:lower:]')
    
    case "$context_lower" in
        *iac*|*infrastructure*)     echo "iac_scan" ;;
        *container*)                echo "container_scan" ;;
        *code*)                     echo "sast" ;;
        *)                          echo "sca" ;;  # Default: Open Source
    esac
}

# Detect Snyk product category from CLI command
detect_snyk_category_from_cmd() {
    local cmd="$1"
    local cmd_lower
    cmd_lower=$(echo "$cmd" | tr '[:upper:]' '[:lower:]')
    
    if echo "$cmd_lower" | grep -q "snyk iac"; then
        echo "iac_scan"
    elif echo "$cmd_lower" | grep -q "snyk container"; then
        echo "container_scan"
    elif echo "$cmd_lower" | grep -q "snyk code"; then
        echo "sast"
    else
        echo "sca"  # Default: snyk test = Open Source
    fi
}

# Write source metadata to a category
write_snyk_source() {
    local category="$1"
    local integration="$2"  # github_app or ci
    local version="${3:-}"  # optional version
    
    if [ -n "$version" ] && [ "$version" != "unknown" ]; then
        jq -n \
            --arg tool "snyk" \
            --arg integration "$integration" \
            --arg version "$version" \
            '{tool: $tool, integration: $integration, version: $version}' | \
            lunar collect -j ".$category.source" -
    else
        jq -n \
            --arg tool "snyk" \
            --arg integration "$integration" \
            '{tool: $tool, integration: $integration}' | \
            lunar collect -j ".$category.source" -
    fi
}
