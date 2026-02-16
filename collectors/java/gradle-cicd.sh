#!/bin/bash
set -e

# Record Gradle commands in CI with Gradle version
# Native-bash: no jq dependency

# Parse LUNAR_CI_COMMAND JSON array into a command string (pure bash)
CMD_STR=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')

# Get Gradle version (best effort)
version=""

# Try gradlew first, then gradle
if [[ -f "./gradlew" ]] && [[ -x "./gradlew" ]]; then
    version=$(./gradlew --version 2>&1 | grep -i "Gradle" | head -n1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -n1 || true)
elif command -v gradle >/dev/null 2>&1; then
    version=$(gradle --version 2>&1 | grep -i "Gradle" | head -n1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -n1 || true)
fi

# Fallback: check gradle/wrapper/gradle-wrapper.properties
if [[ -z "$version" ]] && [[ -f "gradle/wrapper/gradle-wrapper.properties" ]]; then
    version=$(grep -E '^distributionUrl=' gradle/wrapper/gradle-wrapper.properties 2>/dev/null | \
        grep -oE 'gradle-[0-9]+\.[0-9]+(\.[0-9]+)?' | \
        sed 's/gradle-//' | head -n1 || true)
fi

if [[ -n "$version" ]]; then
    lunar collect -j ".lang.java.native.gradle.cicd.cmds" \
        "[{\"cmd\": \"$CMD_STR\", \"version\": \"$version\"}]"
    lunar collect -j ".lang.java.cicd.source" \
        '{"tool": "java", "integration": "ci"}'
fi
