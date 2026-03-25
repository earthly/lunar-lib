#!/bin/bash
set -e

# CI collector - runs native on CI runner, avoid jq and heavy dependencies

if [ -z "$LUNAR_CI_COMMAND" ]; then
    exit 0
fi

CMD_RAW="$LUNAR_CI_COMMAND"

if [[ "$CMD_RAW" == "["* ]]; then
    CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
    CMD_STR="$CMD_RAW"
fi

if echo "$CMD_STR" | grep -qE '^(/usr/bin/)?git\s'; then
    exit 0
fi

if ! echo "$CMD_STR" | grep -qE '(^|/)(codeql|codeql-runner)(\s|$)'; then
    exit 0
fi

CODEQL_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-codeql}"
CODEQL_VERSION=$("$CODEQL_BIN" version --format=terse 2>/dev/null || "$CODEQL_BIN" --version 2>/dev/null || echo "unknown")

CMD_SAFE=$(echo "$CMD_STR" | sed -E \
    -e 's/(--github-auth-stdin|--github-auth|--token)(=| )[^ ]+/\1=<redacted>/Ig')

CMD_ESCAPED=$(echo "$CMD_SAFE" | sed 's/"/\\"/g')

echo "{\"cmds\":[{\"cmd\":\"$CMD_ESCAPED\",\"version\":\"$CODEQL_VERSION\"}]}" | \
    lunar collect -j ".sast.native.codeql.cicd" -

lunar collect ".sast.source.tool" "codeql"
lunar collect ".sast.source.integration" "ci"
if [ -n "$CODEQL_VERSION" ] && [ "$CODEQL_VERSION" != "unknown" ]; then
    lunar collect ".sast.source.version" "$CODEQL_VERSION"
fi
