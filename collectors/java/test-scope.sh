#!/bin/bash
set -e

# Detect Java test scope from Maven/Gradle CI commands
# Native-bash: no jq dependency

# Parse LUNAR_CI_COMMAND JSON array into a command string (pure bash)
CMD_STR=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')

# Default scope is "all" (whole project)
scope="all"

# Maven: -pl or --projects flag means module-specific tests
# Gradle: --tests with a specific pattern means targeted tests
if echo "$CMD_STR" | grep -qE '\s(-pl|--projects)\s'; then
    scope="module"
elif echo "$CMD_STR" | grep -qE '\s--tests\s'; then
    scope="module"
fi

# Collect Java-specific test scope
lunar collect ".lang.java.tests.scope" "$scope"

# Determine which build tool for .testing.source
tool="maven-surefire"
if echo "$CMD_STR" | grep -qE '\b(gradle|gradlew)\b'; then
    tool="gradle-test"
fi

# Collect normalized testing indicator (dual-write)
lunar collect -j ".testing.source" \
    "{\"tool\": \"$tool\", \"integration\": \"ci\"}"
