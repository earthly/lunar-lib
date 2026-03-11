#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Check if this is a PHP project
if ! is_php_project; then
    echo "No PHP project detected, exiting"
    exit 0
fi

deps=()
source_tool="composer"

# Extract dependencies from composer.json
if [[ -f "composer.json" ]]; then
    # Get direct (require) dependencies, excluding php and ext-* entries
    require_deps=$(jq -r '.require // {} | to_entries[] | select(.key | test("^(php|ext-)") | not) | "\(.key)==\(.value)"' composer.json 2>/dev/null || true)

    while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        name="${line%%==*}"
        version="${line#*==}"
        deps+=("$(jq -n --arg path "$name" --arg version "$version" \
            '{path: $path, version: $version, indirect: false}')")
    done <<< "$require_deps"
fi

# Extract dev dependencies from composer.json
dev_deps=()
if [[ -f "composer.json" ]]; then
    require_dev_deps=$(jq -r '.["require-dev"] // {} | to_entries[] | "\(.key)==\(.value)"' composer.json 2>/dev/null || true)

    while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        name="${line%%==*}"
        version="${line#*==}"
        dev_deps+=("$(jq -n --arg path "$name" --arg version "$version" \
            '{path: $path, version: $version}')")
    done <<< "$require_dev_deps"
fi

# Only collect if we found dependencies
if [[ ${#deps[@]} -gt 0 ]] || [[ ${#dev_deps[@]} -gt 0 ]]; then
    direct_json="[]"
    dev_json="[]"
    if [[ ${#deps[@]} -gt 0 ]]; then
        direct_json=$(printf '%s\n' "${deps[@]}" | jq -s '.')
    fi
    if [[ ${#dev_deps[@]} -gt 0 ]]; then
        dev_json=$(printf '%s\n' "${dev_deps[@]}" | jq -s '.')
    fi

    jq -n \
        --argjson direct "$direct_json" \
        --argjson dev "$dev_json" \
        --arg tool "$source_tool" \
        '{
            direct: $direct,
            dev: $dev,
            source: {
                tool: $tool,
                integration: "code"
            }
        }' | lunar collect -j ".lang.php.dependencies" -
else
    echo "No dependencies found"
fi
