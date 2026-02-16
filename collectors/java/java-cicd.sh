#!/bin/bash
set -e

# Record java/javac commands in CI with Java version
# Native-bash: no jq dependency

# Parse LUNAR_CI_COMMAND JSON array into a command string (pure bash)
CMD_STR=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')

# Get Java version (best effort)
# Java version output format varies:
# - Java 8:  java version "1.8.0_291"
# - Java 9+: openjdk version "17.0.1" 2021-10-19
version=$(java -version 2>&1 | head -n1 | sed -n 's/.*version "\([^"]*\)".*/\1/p' || true)

if [[ -n "$version" ]]; then
    lunar collect -j ".lang.java.native.java.cicd.cmds" \
        "[{\"cmd\": \"$CMD_STR\", \"version\": \"$version\"}]"
    lunar collect -j ".lang.java.cicd.source" \
        '{"tool": "java", "integration": "ci"}'
fi
