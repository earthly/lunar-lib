#!/bin/bash
set -e

# Record node commands in CI with Node.js runtime version
# Native-bash: no jq dependency

# Parse LUNAR_CI_COMMAND JSON array into a string using sed
CMD_STR=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')

# Get Node.js version using the exact traced binary
NODE_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-node}"
version=$("$NODE_BIN" -v 2>/dev/null | sed 's/^v//' || echo "")

if [[ -n "$version" ]]; then
    # Escape backslashes and quotes in CMD_STR for safe JSON embedding
    ESCAPED_CMD=$(printf '%s' "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')
    lunar collect -j ".lang.nodejs.cicd.cmds" "[{\"cmd\": \"$ESCAPED_CMD\", \"version\": \"$version\"}]"
fi
