#!/bin/bash
set -e

# Collect Node.js CI/CD command information (native — no jq)
# Parse LUNAR_CI_COMMAND JSON array into a string using sed
CMD_STR=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')

# Get Node.js version — always use "node" (not npm/yarn/pnpm which have their own versions)
# The node binary is in the same BIN_DIR as the traced package manager
NODE_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}node"
version=$("$NODE_BIN" -v 2>/dev/null | sed 's/^v//' || echo "")

if [[ -n "$version" ]]; then
    # Escape backslashes and quotes in CMD_STR for safe JSON embedding
    ESCAPED_CMD=$(printf '%s' "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')
    lunar collect -j ".lang.nodejs.cicd.cmds" "[{\"cmd\": \"$ESCAPED_CMD\", \"version\": \"$version\"}]"
    lunar collect -j ".lang.nodejs.cicd.source" "{\"tool\": \"node\", \"integration\": \"ci\"}"
fi
