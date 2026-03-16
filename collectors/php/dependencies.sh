#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Collect PHP dependencies from composer.json
# Note: License information should be collected via SBOM tools (Syft, Trivy, etc.)

if ! is_php_project; then
    echo "No PHP project detected, exiting"
    exit 0
fi

if [[ ! -f "composer.json" ]]; then
    echo "No composer.json found, exiting"
    exit 0
fi

direct_deps=()
dev_deps=()

# Extract require dependencies (direct)
while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    name=$(echo "$line" | jq -r '.key')
    version=$(echo "$line" | jq -r '.value')
    # Skip php and ext-* entries (platform requirements, not packages)
    [[ "$name" == "php" ]] && continue
    [[ "$name" == ext-* ]] && continue
    direct_deps+=("$(jq -n --arg path "$name" --arg version "$version" \
        '{path: $path, version: $version}')")
done < <(jq -c '.require // {} | to_entries[] | {key: .key, value: .value}' composer.json 2>/dev/null)

# Extract require-dev dependencies (dev)
while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    name=$(echo "$line" | jq -r '.key')
    version=$(echo "$line" | jq -r '.value')
    dev_deps+=("$(jq -n --arg path "$name" --arg version "$version" \
        '{path: $path, version: $version, dev: true}')")
done < <(jq -c '.["require-dev"] // {} | to_entries[] | {key: .key, value: .value}' composer.json 2>/dev/null)

# Only collect if we found dependencies
if [[ ${#direct_deps[@]} -gt 0 ]] || [[ ${#dev_deps[@]} -gt 0 ]]; then
    direct_json="[]"
    dev_json="[]"
    if [[ ${#direct_deps[@]} -gt 0 ]]; then
        direct_json=$(printf '%s\n' "${direct_deps[@]}" | jq -s '.')
    fi
    if [[ ${#dev_deps[@]} -gt 0 ]]; then
        dev_json=$(printf '%s\n' "${dev_deps[@]}" | jq -s '.')
    fi

    jq -n \
        --argjson direct "$direct_json" \
        --argjson dev "$dev_json" \
        '{
            direct: $direct,
            dev: $dev,
            source: {
                tool: "composer",
                integration: "code"
            }
        }' | lunar collect -j ".lang.php.dependencies" -
else
    echo "No dependencies found"
fi
