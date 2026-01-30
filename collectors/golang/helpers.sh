#!/bin/bash

# Shared helper functions for the golang collector

# Check if the current directory is a Go project.
# Returns 0 (success) if it's a Go project, 1 (failure) otherwise.
is_go_project() {
    # Quick check: if go.mod exists, it's a Go project
    if [[ -f "go.mod" ]]; then
        return 0
    fi
    # Fall back to checking for .go files (limit depth to avoid slow scans)
    if find . -maxdepth 3 -name "*.go" -type f -not -path './.git/*' 2>/dev/null | head -1 | grep -q .; then
        return 0
    fi
    return 1
}
