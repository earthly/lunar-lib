#!/bin/bash
set -e

# Record Poetry commands in CI with Poetry version
# Native-bash: no jq dependency

# Parse LUNAR_CI_COMMAND JSON array into a command string (pure bash)
CMD_STR=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')

# Escape for safe JSON embedding
CMD_ESCAPED=$(printf '%s' "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

# Get Poetry version using the exact traced binary
POETRY_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-poetry}"
version=$("$POETRY_BIN" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -n1 || echo "")

if [[ -n "$version" ]]; then
    lunar collect -j ".lang.python.poetry.cicd.cmds" "[{\"cmd\":\"$CMD_ESCAPED\",\"version\":\"$version\"}]"
fi
