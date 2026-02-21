#!/bin/bash
set -e

# Collect Python CI/CD command information
# Runs as native (no jq) — parse LUNAR_CI_COMMAND with sed

# Parse the JSON array into a command string
# Note: LUNAR_CI_COMMAND is a simple JSON array of strings from the CI hook.
# Complex arguments with embedded quotes are uncommon in practice.
CMD_STR=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')

# Use the exact traced binary for version extraction
PYTHON_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-python3}"

# Get Python version
version=$("$PYTHON_BIN" --version 2>/dev/null | awk '{print $2}' || echo "")

if [[ -n "$version" ]]; then
    # Escape special characters for safe JSON embedding
    CMD_ESCAPED=$(printf '%s' "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')
    lunar collect -j ".lang.python.cicd.cmds" "[{\"cmd\":\"$CMD_ESCAPED\",\"version\":\"$version\"}]"
    lunar collect -j ".lang.python.cicd.source" '{"tool":"python","integration":"ci"}'
fi
