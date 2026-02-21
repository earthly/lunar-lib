#!/bin/bash
set -e

# Record Maven commands in CI with Maven version
# Native-bash: no jq dependency

# Parse LUNAR_CI_COMMAND JSON array into a command string (pure bash)
CMD_STR=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')

# Escape for safe JSON embedding (backslashes then double quotes)
json_cmd=$(echo "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

# Use the exact traced binary for version extraction
MVN_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-mvn}"

# Get Maven version (best effort)
version=$("$MVN_BIN" --version 2>&1 | head -n1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -n1 || true)

# Fallback: Maven wrapper properties
if [[ -z "$version" ]] && [[ -f ".mvn/wrapper/maven-wrapper.properties" ]]; then
    version=$(grep -E '^distributionUrl=' .mvn/wrapper/maven-wrapper.properties 2>/dev/null | \
        grep -oE 'apache-maven-[0-9]+\.[0-9]+\.[0-9]+' | \
        sed 's/apache-maven-//' | head -n1 || true)
fi

# Always collect the command, version may be empty
lunar collect -j ".lang.java.cicd.cmds" \
    "[{\"cmd\": \"$json_cmd\", \"version\": \"$version\", \"tool\": \"maven\"}]"
lunar collect -j ".lang.java.cicd.source" \
    '{"tool": "java", "integration": "ci"}'
