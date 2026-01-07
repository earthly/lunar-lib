#!/bin/bash

set -e

# Function to process a single Dockerfile
process_file() {
    local file="$1"
    
    # Normalize path (remove leading ./)
    local path="${file#./}"
    
    # Parse Dockerfile to JSON AST
    if ! ast=$(dockerfile-json "$file" 2>/dev/null); then
        # Invalid Dockerfile
        jq -n --arg path "$path" '{path: $path, valid: false}'
        return 0
    fi
    
    # Extract base images from all stages
    base_images=$(echo "$ast" | jq '[
        (.Stages // [])[] |
        .From.Image |
        select(. != null and . != "") |
        split(":") as $parts |
        {
            reference: .,
            image: ($parts[0] // .),
            tag: ($parts[1] // null)
        }
    ]')
    
    # Extract final stage information
    final_stage_ast=$(echo "$ast" | jq '(.Stages // []) | last // {}')
    
    final_base_name=$(echo "$final_stage_ast" | jq -r '.BaseName // empty')
    final_base_image=$(echo "$final_stage_ast" | jq -r '.From.Image // empty')
    
    user=$(echo "$final_stage_ast" | jq -r '
        [(.Commands // [])[] | select(.Name == "USER") | .User] | last // empty
    ')
    
    has_healthcheck=$(echo "$final_stage_ast" | jq '
        [(.Commands // [])[] | select(.Name == "HEALTHCHECK")] | length > 0
    ')
    
    # Extract labels from all stages (merged)
    labels=$(echo "$ast" | jq '
        [(.Stages // [])[] |
            (.Commands // [])[] |
            select(.Name == "LABEL") |
            (.Labels // [])[] |
            {(.Key): .Value}
        ] | add // {}
    ')
    
    # Output combined object with definition and native AST
    local ast_file=$(mktemp)
    echo "$ast" > "$ast_file"
    
    jq -n \
        --arg path "$path" \
        --argjson base_images "$base_images" \
        --arg base_name "$final_base_name" \
        --arg base_image "$final_base_image" \
        --arg user "$user" \
        --argjson has_healthcheck "$has_healthcheck" \
        --argjson labels "$labels" \
        --slurpfile ast "$ast_file" \
        '{
            path: $path,
            valid: true,
            base_images: $base_images,
            final_stage: {
                base_name: (if $base_name == "" then null else $base_name end),
                base_image: (if $base_image == "" then null else $base_image end),
                user: (if $user == "" then null else $user end),
                has_healthcheck: $has_healthcheck
            },
            labels: $labels,
            native: {
                ast: $ast[0]
            }
        }'
    
    rm -f "$ast_file"
}

export -f process_file

# Command to find Dockerfiles (from input or default)
FIND_CMD="${LUNAR_VAR_FIND_COMMAND:-find . -type f \( -name Dockerfile -o -name '*.Dockerfile' -o -name 'Dockerfile.*' \)}"

# Process all Dockerfiles in parallel, collect results
eval "$FIND_CMD" 2>/dev/null | parallel -j 4 process_file | jq -s '.' | lunar collect -j ".containers.definitions" -

# Submit source metadata
TOOL_VERSION=$(dockerfile-json --version 2>&1 | head -1 || echo "unknown")
jq -n --arg tool "dockerfile-json" --arg version "$TOOL_VERSION" \
    '{tool: $tool, version: $version}' | lunar collect -j ".containers.source" -
