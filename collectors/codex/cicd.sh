#!/bin/bash
set -e

# Detect Codex CLI invocations in CI.
# Records command string, version, sandbox mode, and approval mode.

source "$(dirname "$0")/helpers.sh"

if [ -z "$LUNAR_CI_COMMAND" ]; then
  exit 0
fi

CMD_STR=$(parse_cmd_str)
TOOL=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\["//; s/".*$//')
VERSION=$(get_tool_version "$TOOL")

SANDBOX=$(extract_flag_value "$CMD_STR" "--sandbox" "-s")
APPROVAL_MODE=$(extract_flag_value "$CMD_STR" "--ask-for-approval" "-a")

JSON="{"
JSON="$JSON\"cmd\": "$(json_escape "$CMD_STR")","
JSON="$JSON\"cmd_args\": $LUNAR_CI_COMMAND,"
JSON="$JSON\"tool\": \"$TOOL\","
JSON="$JSON\"version\": \"$VERSION\""

[ -n "$SANDBOX" ] && JSON="$JSON,\"sandbox\": \"$SANDBOX\""
[ -n "$APPROVAL_MODE" ] && JSON="$JSON,\"approval_mode\": \"$APPROVAL_MODE\""

JSON="$JSON}"

echo "[$JSON]" | lunar collect -j ".ai.native.codex.cicd.cmds" -
