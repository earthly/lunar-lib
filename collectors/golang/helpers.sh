#!/bin/bash

# Shared helper functions for the golang collector

# Check if the current directory is a Go project.
# Requires go.mod — stray .go files alone are not sufficient, since downstream
# scripts (golangci-lint, go list, etc.) need a Go module to function.
is_go_project() {
    [[ -f "go.mod" ]]
}
