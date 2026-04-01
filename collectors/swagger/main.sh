#!/bin/bash

set -e

# Process a single Swagger spec file
process_file() {
    local file="$1"
    local path="${file#./}"

    # Try to parse as YAML or JSON
    if ! content=$(yq -o=json '.' "$file" 2>/dev/null); then
        jq -n --arg path "$path" '{
            type: "swagger",
            path: $path,
            valid: false,
            version: null,
            paths_count: 0,
            schemas_count: 0
        }'
        return 0
    fi

    # Extract the swagger version field — must be "2.0"
    version=$(echo "$content" | jq -r '.swagger // empty')
    if [ -z "$version" ]; then
        # Not a Swagger 2.0 file — skip silently
        return 0
    fi

    # Count paths and definitions (Swagger 2.0 uses "definitions" not "components.schemas")
    paths_count=$(echo "$content" | jq '[.paths // {} | keys[]] | length')
    schemas_count=$(echo "$content" | jq '[.definitions // {} | keys[]] | length')

    jq -n \
        --arg path "$path" \
        --arg version "$version" \
        --argjson paths_count "$paths_count" \
        --argjson schemas_count "$schemas_count" \
        '{
            type: "swagger",
            path: $path,
            valid: true,
            version: $version,
            paths_count: $paths_count,
            schemas_count: $schemas_count
        }'
}

export -f process_file

FIND_CMD="${LUNAR_VAR_FIND_COMMAND:-find . -type f \( -name 'swagger.yaml' -o -name 'swagger.yml' -o -name 'swagger.json' \) -not -path '*/node_modules/*' -not -path '*/vendor/*' -not -path '*/.git/*'}"

results=$(eval "$FIND_CMD" 2>/dev/null | parallel -j 4 process_file | jq -s '.')

result_count=$(echo "$results" | jq 'length' 2>/dev/null || echo 0)
if [ "$result_count" -gt 0 ]; then
    echo "$results" | lunar collect -j ".api.specs" -

    YQ_VERSION=$(yq --version 2>/dev/null | grep -oP '[\d.]+' | head -1 || echo "unknown")
    jq -n --arg version "$YQ_VERSION" \
        '{tool: "swagger", version: "1.0.0", integration: "code", parser: ("yq " + $version)}' \
        | lunar collect -j ".api.source" -
fi
