#!/bin/bash
set -e

# Detect Claude CLI invocations in CI.
# Records command, version, flags. Also writes to ai.code_reviewers[] if
# review-mode is detected (e.g. claude --review).

source "$(dirname "$0")/helpers.sh"

if [ -z "$LUNAR_CI_COMMAND" ]; then
  exit 0
fi

CMD_STR=$(parse_cmd_str)
TOOL=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\["//; s/".*$//')
VERSION=$(get_tool_version "$TOOL")

ALLOWED_TOOLS=$(extract_flag_values "$CMD_STR" "--allowedTools")
DISALLOWED_TOOLS=$(extract_flag_values "$CMD_STR" "--disallowedTools")
TOOLS_RESTRICTION=$(extract_flag_value "$CMD_STR" "--tools")
MCP_CONFIG=$(extract_flag_value "$CMD_STR" "--mcp-config")

# Build JSON — native bash (no jq in CI collectors)
JSON="{"
JSON="$JSON\"cmd\": "$(json_escape "$CMD_STR")","
JSON="$JSON\"cmd_args\": $LUNAR_CI_COMMAND,"
JSON="$JSON\"tool\": \"$TOOL\","
JSON="$JSON\"version\": \"$VERSION\""

[ -n "$ALLOWED_TOOLS" ] && JSON="$JSON,\"allowed_tools\": "$(json_escape "$ALLOWED_TOOLS")""
[ -n "$DISALLOWED_TOOLS" ] && JSON="$JSON,\"disallowed_tools\": "$(json_escape "$DISALLOWED_TOOLS")""
[ -n "$TOOLS_RESTRICTION" ] && JSON="$JSON,\"tools_restriction\": "$(json_escape "$TOOLS_RESTRICTION")""
[ -n "$MCP_CONFIG" ] && JSON="$JSON,\"mcp_config\": "$(json_escape "$MCP_CONFIG")""

JSON="$JSON}"

echo "[$JSON]" | lunar collect -j ".ai.native.claude.cicd.cmds" -

# If review mode detected, also write to normalized code_reviewers
if echo "$CMD_STR" | grep -qE '\-\-review|review-mode|code[._-]review'; then
  echo "{\"tool\":\"claude\",\"check_name\":\"claude-cli-review\",\"detected\":true,\"last_seen\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" | lunar collect -j ".ai.code_reviewers[]" -
fi
