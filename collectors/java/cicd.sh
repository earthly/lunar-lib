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

# Get Java version using the exact traced binary
JAVA_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-java}"
version=""
mapfile -t _jv_lines < <("$JAVA_BIN" -version 2>&1 || true)
version_regex='version[[:space:]]+"([^"]+)"'
if [[ "${_jv_lines[0]:-}" =~ $version_regex ]]; then
    version="${BASH_REMATCH[1]}"
fi

# Always collect the command, version may be empty
lunar collect -j ".lang.java.cicd.cmds" \
    "[{\"cmd\": \"$json_cmd\", \"version\": \"$version\"}]"
