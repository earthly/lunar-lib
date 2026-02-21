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
TRACED_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-rustc}"

# Get version from the traced binary (cargo or rustc)
version=$("$TRACED_BIN" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "")

if [[ -n "$version" ]]; then
    CMD_ESCAPED=$(echo "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

    echo "{\"cmds\":[{\"cmd\":\"$CMD_ESCAPED\",\"version\":\"$version\"}],\"source\":{\"tool\":\"cargo\",\"integration\":\"ci\"}}" | \
        lunar collect -j ".lang.rust.cicd" -
fi
