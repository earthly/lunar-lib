#!/bin/bash

# Shared helper functions for the rust collector

# Check if the current directory is a Rust project.
# Requires Cargo.toml — stray .rs files alone are not sufficient, since
# downstream scripts (clippy, cargo commands) need a Cargo manifest.
is_rust_project() {
    [[ -f "Cargo.toml" ]]
}
