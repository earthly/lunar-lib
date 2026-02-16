#!/bin/bash
set -e

# CI collector - runs native on CI runner, avoid jq and heavy dependencies

# Convert LUNAR_CI_COMMAND from JSON array to string if needed
CMD_RAW="$LUNAR_CI_COMMAND"
if [[ "$CMD_RAW" == "["* ]]; then
    CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
    CMD_STR="$CMD_RAW"
fi

# Collect Go CI/CD command information
version=$(go version 2>/dev/null | awk '{print $3}' | sed 's/go//' || echo "")

if [[ -n "$version" ]]; then
  # Escape quotes in command for JSON safety
  CMD_ESCAPED=$(echo "$CMD_STR" | sed 's/"/\\"/g')

  # Write cicd command entry (no jq required)
  # Multiple go commands in same CI run will each append to the cmds array
  echo "{\"cmds\":[{\"cmd\":\"$CMD_ESCAPED\",\"version\":\"$version\"}],\"source\":{\"tool\":\"go\",\"integration\":\"ci\"}}" | \
    lunar collect -j ".lang.go.cicd" -
fi
