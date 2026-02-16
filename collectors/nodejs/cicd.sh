#!/bin/bash
set -e

# Collect Node.js CI/CD command information (native — no jq)
# Parse LUNAR_CI_COMMAND JSON array into a string using sed
CMD_STR=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')

# Get Node.js version
version=$(node -v 2>/dev/null | sed 's/^v//' || echo "")

if [[ -n "$version" ]]; then
    lunar collect -j ".lang.nodejs.cicd.cmds" "[{\"cmd\": \"$CMD_STR\", \"version\": \"$version\"}]"
    lunar collect -j ".lang.nodejs.cicd.source" "{\"tool\": \"node\", \"integration\": \"ci\"}"
fi
