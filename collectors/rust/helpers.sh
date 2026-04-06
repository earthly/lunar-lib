#!/bin/bash

# Shared helper functions for the rust collector

# Check if the repo contains a Rust project (root or subdirs).
# Requires Cargo.toml — stray .rs files alone are not sufficient, since
# downstream scripts (clippy, cargo commands) need a Cargo manifest.
is_rust_project() {
    [[ -f "Cargo.toml" ]] && return 0
    git ls-files --error-unmatch '**/Cargo.toml' >/dev/null 2>&1
}
