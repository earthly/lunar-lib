#!/bin/bash
set -e

lunar collect ".lang.golang.debug1" "debug1"
lunar collect ".lang.golang.debug1_2" "debug1_2"

cmd_str=$(echo "$LUNAR_CI_COMMAND" | jq -r 'join(" ")')
version=$(go version | awk '{print $3}' | sed 's/go//' || echo "")
if [[ -n "$version" ]]; then
  jq -n \
    --arg cmd "$cmd_str" \
    --arg version "$version" \
    '[{cmd: $cmd, version: $version}]' | \
    lunar collect -j ".lang.go.cicd.cmds" -
fi
