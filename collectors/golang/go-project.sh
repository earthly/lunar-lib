#!/bin/bash

set -e

lunar collect ".lang.golang.debug2" "debug2"
lunar collect ".lang.golang.debug2_2" "debug2_2"

check_go_files() {
    local go_mod_exists=false
    local go_sum_exists=false
    local vendor_exists=false
    local goreleaser_exists=false
    local go_mod_version=""

    # Check for go.mod
    if [[ -f "go.mod" ]]; then
        go_mod_exists=true
        # Extract Go version using go list (preferred over grep)
        go_mod_version=$(go list -m -f '{{.GoVersion}}' 2>/dev/null || true)
    fi

    # Check for go.sum
    if [[ -f "go.sum" ]]; then
        go_sum_exists=true
    fi

    # Check for vendor directory
    if [[ -d "vendor" ]]; then
        vendor_exists=true
    fi

    # Check for goreleaser config
    if [[ -f ".goreleaser.yml" ]] || [[ -f ".goreleaser.yaml" ]]; then
        goreleaser_exists=true
    fi

    # Output results
    jq -n \
        --argjson go_mod_exists "$go_mod_exists" \
        --argjson go_sum_exists "$go_sum_exists" \
        --argjson vendor_exists "$vendor_exists" \
        --argjson goreleaser_exists "$goreleaser_exists" \
        --arg go_mod_version "$go_mod_version" \
        '{
            go_mod: {
                exists: $go_mod_exists,
                version: ($go_mod_version | select(. != ""))
            },
            go_sum: {
                exists: $go_sum_exists
            },
            vendor: {
                exists: $vendor_exists
            },
            goreleaser: {
                exists: $goreleaser_exists
            }
        }'
}

# Main collection process
main() {
    # Check if this is actually a Go project by looking for .go files
    if ! find . -name "*.go" -type f 2>/dev/null | grep -q .; then
        echo "No Go files found, exiting"
        exit 0
    fi
    
    # Check for Go files and structure
    go_files_info=$(check_go_files || echo '{}')

    # Collect version, build_systems at top level and native info (including go_mod_version) under native key
    echo "$go_files_info" | jq '{
        version: (.go_mod.version // ""),
        build_systems: ["go"],
        native: .
    }' | lunar collect -j ".lang.go" -
}

main "$@"

