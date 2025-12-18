#!/bin/bash
set -e

# Join the CI command array into a string
cmd_str=$(echo "$LUNAR_CI_COMMAND" | jq -r 'join(" ")')

# Get Java version (best effort)
# Java version output format varies:
# - Java 8: java version "1.8.0_291"
# - Java 9+: openjdk version "17.0.1" 2021-10-19 or java version "17.0.1" 2021-10-19
# - Java 21+: may show just major version like "21" or "38"
# Extract version from quoted string first, then fall back to version pattern
version=$(java -version 2>&1 | head -n1 | grep -oE 'version "[^"]+"' | sed 's/version "//;s/"//' || java -version 2>&1 | head -n1 | grep -oE '[0-9]+(\.[0-9]+)*(\.[0-9]+)?(_[0-9]+)?' | head -n1 || echo "")

if [[ -n "$version" ]]; then
  jq -n \
    --arg cmd "$cmd_str" \
    --arg version "$version" \
    '[{cmd: $cmd, version: $version}]' | \
    lunar collect -j ".lang.java.native.java.cicd.cmds" -
fi

