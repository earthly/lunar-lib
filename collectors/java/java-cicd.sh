#!/bin/bash
set -e

# Record java/javac commands in CI with Java version
# Native-bash: no jq dependency

# Parse LUNAR_CI_COMMAND JSON array into a command string (pure bash)
CMD_STR=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')

# Escape for safe JSON embedding (backslashes then double quotes)
json_cmd=$(echo "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

# Get Java version (best effort)
version=""
if command -v java >/dev/null 2>&1; then
    version=$(java -version 2>&1 | head -n1 | sed -n 's/.*version "\([^"]*\)".*/\1/p' || true)
fi

# Always collect the command, version may be empty
lunar collect -j ".lang.java.cicd.cmds" \
    "[{\"cmd\": \"$json_cmd\", \"version\": \"$version\", \"tool\": \"java\"}]"
lunar collect -j ".lang.java.cicd.source" \
    '{"tool": "java", "integration": "ci"}'
