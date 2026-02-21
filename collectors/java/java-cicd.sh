#!/bin/bash
set -e

# Record java/javac commands in CI with Java version
# Native-bash: no jq dependency

# Parse LUNAR_CI_COMMAND JSON array into a command string (pure bash)
CMD_STR=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')

# Escape for safe JSON embedding (backslashes then double quotes)
json_cmd=$(echo "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

# Get Java version using the exact traced binary
JAVA_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-java}"
version=$("$JAVA_BIN" -version 2>&1 | head -n1 | sed -n 's/.*version "\([^"]*\)".*/\1/p' || true)

# Always collect the command, version may be empty
lunar collect -j ".lang.java.cicd.cmds" \
    "[{\"cmd\": \"$json_cmd\", \"version\": \"$version\", \"tool\": \"java\"}]"
lunar collect -j ".lang.java.cicd.source" \
    '{"tool": "java", "integration": "ci"}'
