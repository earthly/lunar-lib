#!/bin/bash
set -e

# Collect Go CI/CD command information
cmd_str=$(echo "$LUNAR_CI_COMMAND" | jq -r 'join(" ")')
version=$(go version | awk '{print $3}' | sed 's/go//' || echo "")

if [[ -n "$version" ]]; then
  jq -n \
    --arg cmd "$cmd_str" \
    --arg version "$version" \
    '{
      cmds: [{cmd: $cmd, version: $version}],
      source: {
        tool: "go",
        integration: "ci"
      }
    }' | \
    lunar collect -j ".lang.go.cicd" -
fi
