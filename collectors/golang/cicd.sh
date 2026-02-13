#!/bin/bash
set -e

# CI collector - runs native on CI runner, avoid jq dependency

# Parse LUNAR_CI_COMMAND (may be JSON array or plain string)
if [[ "$LUNAR_CI_COMMAND" == "["* ]]; then
  cmd_str=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
  cmd_str="$LUNAR_CI_COMMAND"
fi

version=$(go version 2>/dev/null | awk '{print $3}' | sed 's/go//' || echo "")

if [[ -n "$version" ]]; then
  # Escape quotes in command for JSON
  cmd_escaped=$(echo "$cmd_str" | sed 's/"/\\"/g')
  echo "{\"cmds\":[{\"cmd\":\"$cmd_escaped\",\"version\":\"$version\"}],\"source\":{\"tool\":\"go\",\"integration\":\"ci\"}}" | \
    lunar collect -j ".lang.go.cicd" -
fi
