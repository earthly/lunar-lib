#!/bin/bash

# Shared helper functions for the PHP collector

# Check if the repo contains a PHP project (root or subdirs).
# Requires composer.json — stray .php files alone are not sufficient,
# since the collector reports on Composer metadata, dependencies, and tooling.
is_php_project() {
    [[ -f "composer.json" ]] && return 0
    git ls-files --error-unmatch '**/composer.json' >/dev/null 2>&1
}
