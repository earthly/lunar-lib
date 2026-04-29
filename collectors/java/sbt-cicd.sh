#!/bin/bash
set -e

# Record sbt commands in CI with sbt version
# Native-bash: no jq dependency

# Parse LUNAR_CI_COMMAND JSON array into a command string (pure bash)
CMD_STR=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')

# Escape for safe JSON embedding (backslashes then double quotes)
json_cmd=$(echo "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

# Use the exact traced binary for version extraction
SBT_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-sbt}"

# Get sbt version (best effort): "sbt script version: 1.9.7"
version=$("$SBT_BIN" --version 2>/dev/null | \
    sed -n 's/.*sbt[[:space:]]\+script[[:space:]]\+version:[[:space:]]*\([0-9.]*\).*/\1/p' | \
    head -n1 || true)

# Fallback: project/build.properties pins sbt.version
if [[ -z "$version" ]] && [[ -f "project/build.properties" ]]; then
    version=$(grep -E '^sbt\.version=' project/build.properties 2>/dev/null | \
        sed 's/^sbt\.version=//' | head -n1 || true)
fi

# Always collect the command, version may be empty
lunar collect -j ".lang.java.sbt.cicd.cmds" \
    "[{\"cmd\": \"$json_cmd\", \"version\": \"$version\"}]"
