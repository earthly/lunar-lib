#!/bin/bash

# Shared helper functions for the nodejs collector

# Check if the repo contains a Node.js project (root or subdirs).
# Requires package.json — the collector reports on npm/yarn metadata,
# dependencies, and tooling that only exist when a manifest is present.
is_nodejs_project() {
    [[ -f "package.json" ]] && return 0
    git ls-files --error-unmatch '**/package.json' >/dev/null 2>&1
}
