#!/bin/bash
set -e

# Record Gradle commands in CI with Gradle version
# Native-bash: no jq dependency

# Parse LUNAR_CI_COMMAND JSON array into a command string (pure bash)
CMD_STR=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')

# Escape for safe JSON embedding (backslashes then double quotes)
json_cmd=$(echo "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

# Use the exact traced binary for version extraction
GRADLE_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-gradle}"

# Get Gradle version (best effort)
version=$("$GRADLE_BIN" --version 2>&1 | grep -i "Gradle" | head -n1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -n1 || true)

# Fallback: check gradle wrapper properties
if [[ -z "$version" ]] && [[ -f "gradle/wrapper/gradle-wrapper.properties" ]]; then
    version=$(grep -E '^distributionUrl=' gradle/wrapper/gradle-wrapper.properties 2>/dev/null | \
        grep -oE 'gradle-[0-9]+\.[0-9]+(\.[0-9]+)?' | \
        sed 's/gradle-//' | head -n1 || true)
fi

# Always collect the command, version may be empty
lunar collect -j ".lang.java.cicd.cmds" \
    "[{\"cmd\": \"$json_cmd\", \"version\": \"$version\", \"tool\": \"gradle\"}]"
lunar collect -j ".lang.java.cicd.source" \
    '{"tool": "java", "integration": "ci"}'
