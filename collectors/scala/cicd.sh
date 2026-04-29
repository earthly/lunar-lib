#!/bin/bash
set -e

# CI collector — runs native on CI runner, avoid jq and heavy dependencies.

CMD_RAW="$LUNAR_CI_COMMAND"
if [[ "$CMD_RAW" == "["* ]]; then
    CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
    CMD_STR="$CMD_RAW"
fi

BIN_NAME="${LUNAR_CI_COMMAND_BIN:-sbt}"
BIN_PATH="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}$BIN_NAME"

# sbt --version → "sbt script version: 1.9.7"
# mill --version → "Mill Build Tool version 0.11.6"
version=""
case "$BIN_NAME" in
    sbt)
        version=$("$BIN_PATH" --version 2>/dev/null | sed -n 's/.*sbt[[:space:]]\+script[[:space:]]\+version:[[:space:]]*\([0-9.]*\).*/\1/p' | head -1)
        ;;
    mill)
        version=$("$BIN_PATH" --version 2>/dev/null | sed -n 's/.*Mill[^0-9]*\([0-9][0-9.]*\).*/\1/p' | head -1)
        ;;
esac

if [[ -n "$version" ]]; then
    CMD_ESCAPED=$(echo "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

    lunar collect -j ".lang.scala.cicd.cmds" \
        "[{\"cmd\": \"$CMD_ESCAPED\", \"version\": \"$version\"}]"
fi
