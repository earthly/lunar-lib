#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Check if this is a Go project
if ! is_go_project; then
    echo "No Go project detected, exiting"
    exit 0
fi

go_mod_exists=false
go_sum_exists=false
vendor_exists=false
goreleaser_exists=false
go_mod_version=""
go_module_path=""

# Check for go.mod
if [[ -f "go.mod" ]]; then
    go_mod_exists=true
    go_mod_version=$(go list -m -f '{{.GoVersion}}' 2>/dev/null || true)
    go_module_path=$(go list -m -f '{{.Path}}' 2>/dev/null || true)
fi

# Check for go.sum
[[ -f "go.sum" ]] && go_sum_exists=true

# Check for vendor directory
[[ -f "vendor/modules.txt" ]] && vendor_exists=true

# Check for goreleaser config
[[ -f ".goreleaser.yml" ]] || [[ -f ".goreleaser.yaml" ]] && goreleaser_exists=true

# Build and collect — flat booleans at .lang.go level (no native wrapper)
jq -n \
    --arg module "$go_module_path" \
    --arg version "$go_mod_version" \
    --argjson go_mod_exists "$go_mod_exists" \
    --argjson go_sum_exists "$go_sum_exists" \
    --argjson vendor_exists "$vendor_exists" \
    --argjson goreleaser_exists "$goreleaser_exists" \
    '{
        build_systems: ["go"],
        go_mod_exists: $go_mod_exists,
        go_sum_exists: $go_sum_exists,
        vendor_exists: $vendor_exists,
        goreleaser_exists: $goreleaser_exists,
        source: {
            tool: "go",
            integration: "code"
        }
    }
    | if $module != "" then .module = $module else . end
    | if $version != "" then .version = $version else . end' | lunar collect -j ".lang.go" -
