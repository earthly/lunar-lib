#!/bin/bash
set -e

# CI collector - runs native on CI runner, avoid jq and heavy dependencies

# Convert LUNAR_CI_COMMAND from JSON array to string if needed
CMD_RAW="$LUNAR_CI_COMMAND"
if [[ "$CMD_RAW" == "["* ]]; then
    CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
    CMD_STR="$CMD_RAW"
fi

# Use the exact traced binary for version extraction
SC_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-shellcheck}"

# Get shellcheck version
version=$("$SC_BIN" --version 2>/dev/null | sed -n 's/^version: //p' || echo "")

if [[ -n "$version" ]]; then
    # Escape for valid JSON
    CMD_ESCAPED=$(echo "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

    # Write cicd command entry
    lunar collect -j ".lang.shell.native.shellcheck.cicd.cmds" \
        "[{\"cmd\": \"$CMD_ESCAPED\", \"version\": \"$version\"}]"
fi
