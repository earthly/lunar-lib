#!/bin/bash
set -e

# Record pip commands in CI with pip version
# Native-bash: no jq dependency

# Parse LUNAR_CI_COMMAND JSON array into a command string (pure bash)
CMD_STR=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')

# Escape for safe JSON embedding
CMD_ESCAPED=$(printf '%s' "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

# Get pip version using the exact traced binary
PIP_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-pip}"
version=$("$PIP_BIN" --version 2>/dev/null | awk '{print $2}' || echo "")

if [[ -n "$version" ]]; then
    lunar collect -j ".lang.python.pip.cicd.cmds" "[{\"cmd\":\"$CMD_ESCAPED\",\"version\":\"$version\"}]"
fi
