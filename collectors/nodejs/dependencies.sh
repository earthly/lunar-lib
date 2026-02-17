#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Check if this is a Node.js project
if ! is_nodejs_project; then
    echo "No package.json found, exiting"
    exit 0
fi

# Determine primary build system for source metadata
build_tool="npm"
if [[ -f "yarn.lock" ]]; then
    build_tool="yarn"
elif [[ -f "pnpm-lock.yaml" ]]; then
    build_tool="pnpm"
fi

# Extract dependencies from package.json
jq -n --slurpfile pkg package.json \
    --arg tool "$build_tool" \
    '{
        direct: (
            ($pkg[0].dependencies // {}) | to_entries | map({path: .key, version: .value})
        ),
        dev: (
            ($pkg[0].devDependencies // {}) | to_entries | map({path: .key, version: .value})
        ),
        source: {
            tool: $tool,
            integration: "code"
        }
    }' | lunar collect -j ".lang.nodejs.dependencies" -
