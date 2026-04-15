#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

if ! is_ruby_project; then
    exit 0
fi

[[ -f "Gemfile" ]] || exit 0

# Parse gem declarations from Gemfile.
# Handles basic patterns: gem 'name', '~> 1.0' with group tracking.
# Complex Ruby DSL (conditionals, platforms blocks) is best-effort.

direct_json="[]"
dev_json="[]"
current_group="default"

while IFS= read -r line; do
    # Strip leading whitespace for matching
    stripped=$(echo "$line" | sed 's/^[[:space:]]*//')

    # Track group blocks: group :development do / group :development, :test do
    if echo "$stripped" | grep -qE "^group[[:space:]]"; then
        current_group=$(echo "$stripped" | sed -n 's/^group[[:space:]]*:\([a-z_]*\).*/\1/p')
        [[ -z "$current_group" ]] && current_group="default"
        continue
    fi

    # End of group block
    if echo "$stripped" | grep -qE "^end[[:space:]]*$"; then
        current_group="default"
        continue
    fi

    # Match gem declarations
    if echo "$stripped" | grep -qE "^gem[[:space:]]"; then
        gem_name=$(echo "$stripped" | sed -n "s/^gem[[:space:]]*['\"]\\([^'\"]*\\)['\"].*/\\1/p")
        gem_version=$(echo "$stripped" | sed -n "s/^gem[[:space:]]*['\"][^'\"]*['\"][[:space:]]*,[[:space:]]*['\"]\\([^'\"]*\\)['\"].*/\\1/p")

        if [[ -n "$gem_name" ]]; then
            entry=$(jq -n --arg n "$gem_name" --arg v "$gem_version" --arg g "$current_group" \
                '{name: $n, version: $v, group: $g}')

            case "$current_group" in
                development|test)
                    dev_json=$(echo "$dev_json" | jq --argjson e "$entry" '. + [$e]')
                    ;;
                *)
                    direct_json=$(echo "$direct_json" | jq --argjson e "$entry" '. + [$e]')
                    ;;
            esac
        fi
    fi
done < Gemfile

# Only collect if we found any gems
total=$(jq -n --argjson d "$direct_json" --argjson v "$dev_json" '$d + $v | length')
if [[ "$total" -gt 0 ]]; then
    jq -n \
        --argjson direct "$direct_json" \
        --argjson development "$dev_json" \
        '{
            direct: $direct,
            development: $development,
            source: { tool: "bundler", integration: "code" }
        }' | lunar collect -j ".lang.ruby.dependencies" -
fi
