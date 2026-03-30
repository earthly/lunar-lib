#!/bin/bash
set -e

# Record dotnet commands in CI with .NET SDK version
# Native-bash: no jq dependency

# Parse LUNAR_CI_COMMAND JSON array into a command string (pure bash)
CMD_STR=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')

# Escape for safe JSON embedding (backslashes then double quotes)
json_cmd=$(echo "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

# Get .NET SDK version using the exact traced binary
DOTNET_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-dotnet}"
version=$("$DOTNET_BIN" --version 2>/dev/null || true)

# Always collect the command, version may be empty
lunar collect -j ".lang.dotnet.cicd.cmds" \
    "[{\"cmd\": \"$json_cmd\", \"version\": \"$version\"}]"
lunar collect -j ".lang.dotnet.cicd.source" \
    '{"tool": "dotnet", "integration": "ci"}'