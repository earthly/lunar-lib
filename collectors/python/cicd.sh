#!/bin/bash
set -e

# Collect Python CI/CD command information
# Runs as native (no jq) — parse LUNAR_CI_COMMAND with sed

# Parse the JSON array into a command string
CMD_STR=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')

# Get Python version if available
version=$(python3 --version 2>/dev/null | awk '{print $2}' || python --version 2>/dev/null | awk '{print $2}' || echo "")

if [[ -n "$version" ]]; then
    lunar collect -j ".lang.python.cicd.cmds" "[{\"cmd\":\"$CMD_STR\",\"version\":\"$version\"}]"
    lunar collect -j ".lang.python.cicd.source" '{"tool":"python","integration":"ci"}'
fi
