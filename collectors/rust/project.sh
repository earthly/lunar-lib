#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

if ! is_rust_project; then
    echo "No Rust project detected, exiting"
    exit 0
fi

cargo_toml_exists=false
cargo_lock_exists=false
rust_toolchain_exists=false
clippy_configured=false
rustfmt_configured=false
is_application=false
is_library=false
edition=""
msrv=""
version=""

# Core file detection
[[ -f "Cargo.toml" ]] && cargo_toml_exists=true
[[ -f "Cargo.lock" ]] && cargo_lock_exists=true
[[ -f "rust-toolchain.toml" ]] || [[ -f "rust-toolchain" ]] && rust_toolchain_exists=true
[[ -f "clippy.toml" ]] || [[ -f ".clippy.toml" ]] && clippy_configured=true
[[ -f "rustfmt.toml" ]] || [[ -f ".rustfmt.toml" ]] && rustfmt_configured=true

# Parse Cargo.toml for metadata
if [[ "$cargo_toml_exists" == "true" ]]; then
    # Edition
    edition=$(grep -oP '^\s*edition\s*=\s*"\K[^"]+' Cargo.toml 2>/dev/null || true)

    # MSRV (rust-version field)
    msrv=$(grep -oP '^\s*rust-version\s*=\s*"\K[^"]+' Cargo.toml 2>/dev/null || true)

    # Detect binary targets: [[bin]] section or src/main.rs
    if grep -q '^\[\[bin\]\]' Cargo.toml 2>/dev/null || [[ -f "src/main.rs" ]]; then
        is_application=true
    fi

    # Detect library target: [lib] section or src/lib.rs
    if grep -q '^\[lib\]' Cargo.toml 2>/dev/null || [[ -f "src/lib.rs" ]]; then
        is_library=true
    fi

    # If neither detected, default based on src/main.rs existence
    if [[ "$is_application" == "false" ]] && [[ "$is_library" == "false" ]]; then
        if [[ -f "src/main.rs" ]]; then
            is_application=true
        elif [[ -f "src/lib.rs" ]]; then
            is_library=true
        fi
    fi
fi

# Get Rust version from rust-toolchain.toml or rustc
if [[ -f "rust-toolchain.toml" ]]; then
    version=$(grep -oP '^\s*channel\s*=\s*"\K[^"]+' rust-toolchain.toml 2>/dev/null || true)
elif [[ -f "rust-toolchain" ]]; then
    version=$(cat rust-toolchain | tr -d '[:space:]')
fi
if [[ -z "$version" ]]; then
    version=$(rustc --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' || true)
fi

# Detect workspace
workspace_json="null"
if grep -q '^\[workspace\]' Cargo.toml 2>/dev/null; then
    # Extract workspace members
    members_json=$(grep -A 50 '^\[workspace\]' Cargo.toml | \
        grep -oP '^\s*members\s*=\s*\[.*?\]' | \
        grep -oP '"[^"]+"' | \
        sed 's/"//g' | \
        jq -R -s 'split("\n") | map(select(length > 0))' 2>/dev/null || echo '[]')
    workspace_json=$(jq -n --argjson members "$members_json" '{is_workspace: true, members: $members}')
fi

# Count unsafe blocks in .rs files
unsafe_json=$(grep -rn 'unsafe\s*{' --include='*.rs' src/ 2>/dev/null | \
    grep -v '^\s*//' | \
    jq -R -s 'split("\n") | map(select(length > 0)) |
    map(capture("^(?<file>[^:]+):(?<line>[0-9]+):")) |
    {count: length, locations: map({file: .file, line: (.line | tonumber)})}' 2>/dev/null || echo '{"count": 0, "locations": []}')

# Build and collect
jq -n \
    --arg edition "$edition" \
    --arg msrv "$msrv" \
    --arg version "$version" \
    --argjson cargo_toml_exists "$cargo_toml_exists" \
    --argjson cargo_lock_exists "$cargo_lock_exists" \
    --argjson rust_toolchain_exists "$rust_toolchain_exists" \
    --argjson clippy_configured "$clippy_configured" \
    --argjson rustfmt_configured "$rustfmt_configured" \
    --argjson is_application "$is_application" \
    --argjson is_library "$is_library" \
    --argjson workspace "$workspace_json" \
    --argjson unsafe_blocks "$unsafe_json" \
    '{
        build_systems: ["cargo"],
        cargo_toml_exists: $cargo_toml_exists,
        cargo_lock_exists: $cargo_lock_exists,
        rust_toolchain_exists: $rust_toolchain_exists,
        clippy_configured: $clippy_configured,
        rustfmt_configured: $rustfmt_configured,
        is_application: $is_application,
        is_library: $is_library,
        workspace: $workspace,
        unsafe_blocks: $unsafe_blocks,
        source: {
            tool: "cargo",
            integration: "code"
        }
    }
    | if $edition != "" then .edition = $edition else . end
    | if $msrv != "" then .msrv = $msrv else . end
    | if $version != "" then .version = $version else . end' | lunar collect -j ".lang.rust" -
