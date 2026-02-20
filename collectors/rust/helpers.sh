#!/bin/bash

# Shared helper functions for the rust collector

# Check if the current directory is a Rust project.
# Returns 0 (success) if it's a Rust project, 1 (failure) otherwise.
is_rust_project() {
    if [[ -f "Cargo.toml" ]]; then
        return 0
    fi
    if find . -maxdepth 3 -name "*.rs" -type f -not -path './.git/*' 2>/dev/null | head -1 | grep -q .; then
        return 0
    fi
    return 1
}
