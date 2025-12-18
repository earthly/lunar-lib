#!/bin/bash
set -e

# Join the CI command array into a string
cmd_str=$(echo "$LUNAR_CI_COMMAND" | jq -r 'join(" ")')

# Get Gradle version (best effort)
# Gradle version output format: 
# Gradle 8.5
# or from gradlew: 
# ------------------------------------------------------------
# Gradle 8.5
# ------------------------------------------------------------
# Extract version number from the output
# Try gradlew first (if available), then gradle
if [[ -f "./gradlew" ]] && [[ -x "./gradlew" ]]; then
  version=$(./gradlew --version 2>&1 | grep -i "Gradle" | head -n1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -n1 || echo "")
elif command -v gradle >/dev/null 2>&1; then
  version=$(gradle --version 2>&1 | grep -i "Gradle" | head -n1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -n1 || echo "")
else
  version=""
fi

if [[ -n "$version" ]]; then
  jq -n \
    --arg cmd "$cmd_str" \
    --arg version "$version" \
    '[{cmd: $cmd, version: $version}]' | \
    lunar collect -j ".lang.java.native.gradle.cicd.cmds" -
fi

