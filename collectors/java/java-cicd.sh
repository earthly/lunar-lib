#!/bin/bash
set -e

# Record java/javac commands in CI with Java version
# Native-bash: no jq dependency

# Parse LUNAR_CI_COMMAND JSON array into a command string (pure bash)
CMD_STR=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')

echo "java-cicd: command=$CMD_STR" >&2

# Get Java version (best effort)
version=""
if command -v java >/dev/null 2>&1; then
    version=$(java -version 2>&1 | head -n1 | sed -n 's/.*version "\([^"]*\)".*/\1/p' || true)
    echo "java-cicd: detected version=$version" >&2
else
    echo "java-cicd: java not on PATH" >&2
fi

# Always collect the command, version may be empty
lunar collect -j ".lang.java.native.java.cicd.cmds" \
    "[{\"cmd\": \"$CMD_STR\", \"version\": \"$version\"}]"
lunar collect -j ".lang.java.cicd.source" \
    '{"tool": "java", "integration": "ci"}'
