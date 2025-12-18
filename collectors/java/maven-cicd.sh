#!/bin/bash
set -e

# Join the CI command array into a string
cmd_str=$(echo "$LUNAR_CI_COMMAND" | jq -r 'join(" ")')

echo "maven-cicd: Checking for mvn command..." >&2
echo "maven-cicd: PATH=$PATH" >&2
echo "maven-cicd: MAVEN_HOME=$MAVEN_HOME" >&2
echo "maven-cicd: M2_HOME=$M2_HOME" >&2

# Determine which mvn command to use
MVN_CMD=""
MVN_METHOD=""
# Method 1: Check if mvn is in PATH
if command -v mvn >/dev/null 2>&1; then
  MVN_CMD=$(command -v mvn)
  MVN_METHOD="PATH (command -v)"
  echo "maven-cicd: Found mvn in PATH: $MVN_CMD" >&2
# Method 2: Check MAVEN_HOME or M2_HOME environment variables
elif [[ -n "$MAVEN_HOME" ]] && [[ -x "$MAVEN_HOME/bin/mvn" ]]; then
  MVN_CMD="$MAVEN_HOME/bin/mvn"
  MVN_METHOD="MAVEN_HOME"
  echo "maven-cicd: Found mvn via MAVEN_HOME: $MVN_CMD" >&2
elif [[ -n "$M2_HOME" ]] && [[ -x "$M2_HOME/bin/mvn" ]]; then
  MVN_CMD="$M2_HOME/bin/mvn"
  MVN_METHOD="M2_HOME"
  echo "maven-cicd: Found mvn via M2_HOME: $MVN_CMD" >&2
# Method 3: Check for Maven wrapper in current directory
elif [[ -f "./mvnw" ]] && [[ -x "./mvnw" ]]; then
  MVN_CMD="./mvnw"
  MVN_METHOD="Maven wrapper (./mvnw)"
  echo "maven-cicd: Found mvn via Maven wrapper: $MVN_CMD" >&2
# Method 4: Try to extract mvn path from LUNAR_CI_COMMAND
# The command might be like: /opt/actions-runner/_work/_tool/maven/3.9.6/x64/bin/mvn clean install
# or: /bin/sh /opt/.../mvn --version
else
  echo "maven-cicd: mvn not in PATH, checking LUNAR_CI_COMMAND: $cmd_str" >&2
  while IFS= read -r word; do
    # Check if this word ends with /mvn or /mvnw and is executable
    if [[ "$word" =~ /(mvn|mvnw)$ ]] && [[ -x "$word" ]]; then
      MVN_CMD="$word"
      MVN_METHOD="Extracted from LUNAR_CI_COMMAND"
      echo "maven-cicd: Found mvn path in command: $MVN_CMD" >&2
      break
    fi
  done < <(echo "$cmd_str" | tr ' ' '\n')
  
  if [[ -z "$MVN_CMD" ]]; then
    echo "maven-cicd: Could not find mvn command" >&2
  fi
fi

if [[ -n "$MVN_CMD" ]]; then
  echo "maven-cicd: Using mvn command: $MVN_CMD (method: $MVN_METHOD)" >&2
fi

# Get Maven version (best effort)
# Try multiple methods:
# 1. Extract version from installation path (e.g., /opt/.../maven/3.9.6/.../mvn)
# 2. Check .mvn/wrapper/maven-wrapper.properties file
# 3. Run mvn --version command
version=""
VERSION_METHOD=""

# Method 1: Extract version from path if it's in a structured path like maven/3.9.6/
if [[ -n "$MVN_CMD" ]] && [[ "$MVN_CMD" =~ /maven/([0-9]+\.[0-9]+\.[0-9]+)/ ]]; then
  version="${BASH_REMATCH[1]}"
  VERSION_METHOD="Extracted from path"
  echo "maven-cicd: Extracted version from path: $version" >&2
fi

# Method 2: Check Maven wrapper properties file
if [[ -z "$version" ]] && [[ -f ".mvn/wrapper/maven-wrapper.properties" ]]; then
  echo "maven-cicd: Checking .mvn/wrapper/maven-wrapper.properties" >&2
  # Extract version from distributionUrl, e.g., https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/3.9.6/apache-maven-3.9.6-bin.zip
  wrapper_version=$(grep -E '^distributionUrl=' .mvn/wrapper/maven-wrapper.properties 2>/dev/null | \
    grep -oE 'apache-maven-[0-9]+\.[0-9]+\.[0-9]+' | \
    sed 's/apache-maven-//' | head -n1)
  if [[ -n "$wrapper_version" ]]; then
    version="$wrapper_version"
    VERSION_METHOD="Maven wrapper properties"
    echo "maven-cicd: Extracted version from wrapper properties: $version" >&2
  fi
fi

# Method 3: Run mvn --version command as fallback
if [[ -z "$version" ]] && [[ -n "$MVN_CMD" ]]; then
  echo "maven-cicd: Running $MVN_CMD --version to get version" >&2
  version=$($MVN_CMD --version 2>&1 | head -n1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -n1 || echo "")
  if [[ -n "$version" ]]; then
    VERSION_METHOD="mvn --version command"
    echo "maven-cicd: Extracted version from mvn --version: $version" >&2
  else
    echo "maven-cicd: Failed to extract version from mvn --version" >&2
  fi
fi

if [[ -n "$version" ]]; then
  echo "maven-cicd: Final version: $version (method: $VERSION_METHOD)" >&2
else
  echo "maven-cicd: Could not determine Maven version" >&2
fi

if [[ -n "$version" ]]; then
  jq -n \
    --arg cmd "$cmd_str" \
    --arg version "$version" \
    '[{cmd: $cmd, version: $version}]' | \
    lunar collect -j ".lang.java.native.maven.cicd.cmds" -
fi
