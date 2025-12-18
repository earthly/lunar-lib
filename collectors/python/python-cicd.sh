#!/bin/bash
set -e

# Join the CI command array into a string
cmd_str=$(echo "$LUNAR_CI_COMMAND" | jq -r 'join(" ")')

# Get Python version if available
version=$(python3 --version 2>/dev/null | awk '{print $2}' || python --version 2>/dev/null | awk '{print $2}' || echo "")

# Collect if we have a version
if [[ -n "$version" ]]; then
  jq -n \
    --arg cmd "$cmd_str" \
    --arg version "$version" \
    '[{cmd: $cmd, version: $version}]' | \
    lunar collect -j ".lang.python.cicd.cmds" -
fi

