#!/bin/bash
set -e

# CI collector — runs native on the CI runner, avoid jq and heavy dependencies.

CMD_RAW="$LUNAR_CI_COMMAND"
if [[ "$CMD_RAW" == "["* ]]; then
    CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
    CMD_STR="$CMD_RAW"
fi

BIN_NAME="${LUNAR_CI_COMMAND_BIN:-kotlinc}"
BIN_PATH="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}$BIN_NAME"

# kotlinc -version → (stderr) "info: kotlinc-jvm 1.9.22 (JRE 17.0.2+8)"
# kotlin  -version → (stderr) "Kotlin version 1.9.22-release-..."
version=$("$BIN_PATH" -version 2>&1 | sed -n 's/.*kotlin[c-]*[- ]*[a-z]*[[:space:]]*\([0-9][0-9.]*\).*/\1/p' | head -1)

if [[ -n "$version" ]]; then
    CMD_ESCAPED=$(echo "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

    lunar collect -j ".lang.kotlin.cicd.cmds" \
        "[{\"cmd\": \"$CMD_ESCAPED\", \"version\": \"$version\"}]"
fi
