#!/bin/bash
set -e

# OpenAPI/Swagger collector — finds spec files, extracts metadata,
# writes to .api.spec_files and .api.native.openapi

FIND_CMD="${LUNAR_VAR_FIND_COMMAND:-find . -type f \( -name 'openapi.yaml' -o -name 'openapi.yml' -o -name 'openapi.json' -o -name 'swagger.yaml' -o -name 'swagger.yml' -o -name 'swagger.json' \) -not -path '*/node_modules/*' -not -path '*/vendor/*' -not -path '*/.git/*'}"

SPEC_FILES=$(eval "$FIND_CMD" 2>/dev/null || true)

if [ -z "$SPEC_FILES" ]; then
    echo "No OpenAPI/Swagger spec files found"
    exit 0
fi

# Temp files for accumulating results
NATIVE_MAP=$(mktemp)
echo '{}' > "$NATIVE_MAP"
trap 'rm -f "$NATIVE_MAP"' EXIT

while IFS= read -r file; do
    [ -z "$file" ] && continue

    # Normalize path — strip leading ./
    filepath="${file#./}"

    # Determine file type and parse to JSON
    raw_json=""
    valid=true
    case "$file" in
        *.json)
            raw_json=$(jq '.' "$file" 2>/dev/null) || valid=false
            ;;
        *.yaml|*.yml)
            raw_json=$(yq -o=json '.' "$file" 2>/dev/null) || valid=false
            ;;
    esac

    if [ "$valid" = "false" ] || [ -z "$raw_json" ]; then
        # File exists but failed to parse — still record it
        jq -n \
            --arg path "$filepath" \
            '[{
                path: $path,
                format: "unknown",
                protocol: "rest",
                valid: false,
                version: null,
                operation_count: 0,
                schema_count: 0,
                has_docs: false
            }]' | lunar collect -j ".api.spec_files" -
        continue
    fi

    # Detect format and version from spec content
    openapi_ver=$(echo "$raw_json" | jq -r '.openapi // empty' 2>/dev/null || true)
    swagger_ver=$(echo "$raw_json" | jq -r '.swagger // empty' 2>/dev/null || true)

    if [ -n "$openapi_ver" ]; then
        format="openapi"
        version="$openapi_ver"
    elif [ -n "$swagger_ver" ]; then
        format="swagger"
        version="$swagger_ver"
    else
        format="unknown"
        version=""
        valid=false
    fi

    # Count operations (HTTP methods across all paths)
    operation_count=$(echo "$raw_json" | jq '
        [.paths // {} | to_entries[] | .value | to_entries[]
         | select(.key | test("^(get|put|post|delete|patch|options|head|trace)$"))]
        | length' 2>/dev/null || echo "0")

    # Count schemas — OAS3 uses components.schemas, Swagger 2 uses definitions
    schema_count=$(echo "$raw_json" | jq '
        ((.components.schemas // {}) | length) +
        ((.definitions // {}) | length)' 2>/dev/null || echo "0")

    # Collect spec_files entry as a single-element array (auto-merges across calls)
    jq -n \
        --arg path "$filepath" \
        --arg format "$format" \
        --arg version "$version" \
        --argjson valid "$valid" \
        --argjson op_count "$operation_count" \
        --argjson schema_count "$schema_count" \
        '[{
            path: $path,
            format: $format,
            protocol: "rest",
            valid: $valid,
            version: $version,
            operation_count: $op_count,
            schema_count: $schema_count,
            has_docs: true
        }]' | lunar collect -j ".api.spec_files" -

    # Accumulate native specs into a single map (to avoid dot-in-filename path issues)
    NATIVE_MAP_NEW=$(jq --arg key "$filepath" --argjson val "$raw_json" \
        '. + {($key): $val}' "$NATIVE_MAP")
    echo "$NATIVE_MAP_NEW" > "$NATIVE_MAP"

done <<< "$SPEC_FILES"

# Collect the full native.openapi map in one shot
lunar collect -j ".api.native.openapi" - < "$NATIVE_MAP"

# Source metadata
lunar collect ".api.source.tool" "openapi-collector"
lunar collect ".api.source.integration" "code"
