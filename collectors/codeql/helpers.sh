#!/bin/bash

write_codeql_source() {
    local integration="$1"
    local version="${2:-}"

    if [ -n "$version" ] && [ "$version" != "unknown" ]; then
        jq -n \
            --arg tool "codeql" \
            --arg integration "$integration" \
            --arg version "$version" \
            '{tool: $tool, integration: $integration, version: $version}' | \
            lunar collect -j ".sast.source" -
    else
        jq -n \
            --arg tool "codeql" \
            --arg integration "$integration" \
            '{tool: $tool, integration: $integration}' | \
            lunar collect -j ".sast.source" -
    fi
}
