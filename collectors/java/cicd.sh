#!/bin/bash
set -e

# Record java/javac commands in CI with Java version
# Native-bash: no jq or sed dependency (minimal CI environments may lack both)

# Parse LUNAR_CI_COMMAND JSON array into a command string (pure bash)
CMD_STR="${LUNAR_CI_COMMAND#\[}"        # strip leading [
CMD_STR="${CMD_STR%\]}"                 # strip trailing ]
CMD_STR="${CMD_STR//\",\"/ }"           # "," separators -> space
CMD_STR="${CMD_STR//\"/}"               # drop remaining quotes

# Escape for safe JSON embedding (backslashes then double quotes)
json_cmd="${CMD_STR//\\/\\\\}"
json_cmd="${json_cmd//\"/\\\"}"

# Get Java version using the exact traced binary. `java -version` prints
# `openjdk version "21.0.5" ...` and `javac -version` prints `javac 21.0.5`,
# either one possibly after a "Picked up JAVA_TOOL_OPTIONS: ..." line.
JAVA_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-java}"
version=""
java_regex='version[[:space:]]+"([^"]+)"'
javac_regex='^javac[[:space:]]+([^[:space:]]+)'
while IFS= read -r line; do
    if [[ "$line" =~ $java_regex ]] || [[ "$line" =~ $javac_regex ]]; then
        version="${BASH_REMATCH[1]}"
        break
    fi
done < <("$JAVA_BIN" -version 2>&1 || true)

# Always collect the command, version may be empty
lunar collect -j ".lang.java.cicd.cmds" \
    "[{\"cmd\": \"$json_cmd\", \"version\": \"$version\"}]"
