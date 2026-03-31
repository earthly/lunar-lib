#!/bin/bash

# Shared helper functions for the golang collector

# Check if the repo contains a Go project (root or subdirs).
# Requires go.mod — stray .go files alone are not sufficient, since downstream
# scripts (golangci-lint, go list, etc.) need a Go module to function.
is_go_project() {
    [[ -f "go.mod" ]] && return 0
    git ls-files --error-unmatch '**/go.mod' >/dev/null 2>&1
}
