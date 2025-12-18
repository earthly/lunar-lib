#!/bin/bash
set -e

# Join the CI command array into a string
cmd_str=$(echo "$LUNAR_CI_COMMAND" | jq -r 'join(" ")')

# Get Node.js version if available
version=$(node -v 2>/dev/null | sed 's/^v//' || echo "")

if [[ -n "$version" ]]; then
  jq -n \
    --arg cmd "$cmd_str" \
    --arg version "$version" \
    '[{cmd: $cmd, version: $version}]' | \
    lunar collect -j ".lang.nodejs.cicd.cmds" -
fi

