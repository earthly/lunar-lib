#!/bin/bash

# Shared helper functions for the php collector

# Check if the current directory is a PHP project.
# Returns 0 (success) if it's a PHP project, 1 (failure) otherwise.
is_php_project() {
    # Quick check: if composer.json exists, it's a PHP project
    if [[ -f "composer.json" ]]; then
        return 0
    fi
    # Fall back to checking for .php files (limit depth to avoid slow scans)
    if find . -maxdepth 3 -name "*.php" -type f -not -path './.git/*' -not -path './vendor/*' 2>/dev/null | head -1 | grep -q .; then
        return 0
    fi
    return 1
}
