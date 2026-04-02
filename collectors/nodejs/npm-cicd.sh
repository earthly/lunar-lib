#!/bin/bash
set -e

# Record npm/npx commands in CI with npm version
# Native-bash: no jq dependency

# Parse LUNAR_CI_COMMAND JSON array into a command string (pure bash)
CMD_STR=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')

# Escape for safe JSON embedding
ESCAPED_CMD=$(printf '%s' "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

# Get npm version using the exact traced binary
NPM_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-npm}"
version=$("$NPM_BIN" --version 2>/dev/null || echo "")

if [[ -n "$version" ]]; then
    lunar collect -j ".lang.nodejs.npm.cicd.cmds" "[{\"cmd\": \"$ESCAPED_CMD\", \"version\": \"$version\"}]"
fi
