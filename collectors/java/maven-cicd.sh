#!/bin/bash
set -e

# Record Maven commands in CI with Maven version
# Native-bash: no jq dependency

# Parse LUNAR_CI_COMMAND JSON array into a command string (pure bash)
CMD_STR=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')

# Escape for safe JSON embedding (backslashes then double quotes)
json_cmd=$(echo "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

# Determine which mvn command to use
MVN_CMD=""

if command -v mvn >/dev/null 2>&1; then
    MVN_CMD=$(command -v mvn)
elif [[ -n "$MAVEN_HOME" ]] && [[ -x "$MAVEN_HOME/bin/mvn" ]]; then
    MVN_CMD="$MAVEN_HOME/bin/mvn"
elif [[ -n "$M2_HOME" ]] && [[ -x "$M2_HOME/bin/mvn" ]]; then
    MVN_CMD="$M2_HOME/bin/mvn"
elif [[ -f "./mvnw" ]] && [[ -x "./mvnw" ]]; then
    MVN_CMD="./mvnw"
else
    # Try extracting mvn path from the CI command
    for word in $CMD_STR; do
        if [[ "$word" =~ /(mvn|mvnw)$ ]] && [[ -x "$word" ]]; then
            MVN_CMD="$word"
            break
        fi
    done
fi

# Get Maven version (best effort, multiple methods)
version=""

# Method 1: Extract from installation path (matches /maven/3.9.6/ or /apache-maven-3.9.6/)
if [[ -n "$MVN_CMD" ]] && [[ "$MVN_CMD" =~ maven[-/]([0-9]+\.[0-9]+\.[0-9]+) ]]; then
    version="${BASH_REMATCH[1]}"
fi
# Also try extracting from CMD_STR (the CI command may contain the full path)
if [[ -z "$version" ]] && [[ "$CMD_STR" =~ maven[-/]([0-9]+\.[0-9]+\.[0-9]+) ]]; then
    version="${BASH_REMATCH[1]}"
fi

# Method 2: Maven wrapper properties
if [[ -z "$version" ]] && [[ -f ".mvn/wrapper/maven-wrapper.properties" ]]; then
    version=$(grep -E '^distributionUrl=' .mvn/wrapper/maven-wrapper.properties 2>/dev/null | \
        grep -oE 'apache-maven-[0-9]+\.[0-9]+\.[0-9]+' | \
        sed 's/apache-maven-//' | head -n1 || true)
fi

# Method 3: Run mvn --version
if [[ -z "$version" ]] && [[ -n "$MVN_CMD" ]]; then
    version=$($MVN_CMD --version 2>&1 | head -n1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -n1 || true)
fi

# Always collect the command, version may be empty
lunar collect -j ".lang.java.native.maven.cicd.cmds" \
    "[{\"cmd\": \"$json_cmd\", \"version\": \"$version\"}]"
lunar collect -j ".lang.java.cicd.source" \
    '{"tool": "java", "integration": "ci"}'
