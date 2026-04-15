#!/bin/bash
set -e

# Collect Rake CI/CD command information
# Runs as native (no jq) — parse LUNAR_CI_COMMAND with sed

CMD_STR=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')

# Get Rake version using the exact traced binary
RAKE_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-rake}"
version=$("$RAKE_BIN" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9.]+' | head -1 || echo "")

if [[ -n "$version" ]]; then
    CMD_ESCAPED=$(printf '%s' "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')
    lunar collect -j ".lang.ruby.rake.cicd.cmds" "[{\"cmd\":\"$CMD_ESCAPED\",\"version\":\"$version\"}]"
fi
