#!/bin/bash

# Shared helper functions for the nodejs collector

# Check if the current directory is a Node.js project.
# Returns 0 (success) if it's a Node.js project, 1 (failure) otherwise.
is_nodejs_project() {
    if [[ -f "package.json" ]]; then
        return 0
    fi
    return 1
}
