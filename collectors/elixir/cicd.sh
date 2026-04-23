#!/bin/bash
set -e

# CI collector — runs native on CI runner, avoid jq and heavy dependencies

# Convert LUNAR_CI_COMMAND from JSON array to string if needed
CMD_RAW="$LUNAR_CI_COMMAND"
if [[ "$CMD_RAW" == "["* ]]; then
    CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
    CMD_STR="$CMD_RAW"
fi

# Resolve the elixir binary alongside mix (the hook fires on `mix`).
ELIXIR_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}elixir"
version=$("$ELIXIR_BIN" --version 2>/dev/null | sed -n 's/^Elixir[[:space:]]\([0-9.]*\).*/\1/p' | head -1)

if [[ -n "$version" ]]; then
    CMD_ESCAPED=$(echo "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

    lunar collect -j ".lang.elixir.cicd.cmds" \
        "[{\"cmd\": \"$CMD_ESCAPED\", \"version\": \"$version\"}]"
fi
