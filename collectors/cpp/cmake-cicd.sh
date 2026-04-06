#!/bin/bash
set -e

# CI collector — runs native, no jq available

CMD_RAW="$LUNAR_CI_COMMAND"
if [[ "$CMD_RAW" == "["* ]]; then
    CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
    CMD_STR="$CMD_RAW"
fi

CMAKE_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-cmake}"

version=$("$CMAKE_BIN" --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "")

if [[ -n "$version" ]]; then
    CMD_ESCAPED=$(echo "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

    echo "{\"cmds\":[{\"cmd\":\"$CMD_ESCAPED\",\"version\":\"$version\"}],\"source\":{\"tool\":\"cpp\",\"integration\":\"ci\"}}" | \
      lunar collect -j ".lang.cpp.cicd" -
fi
