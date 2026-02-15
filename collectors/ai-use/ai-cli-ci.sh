#!/bin/bash
set -e

# Detect AI CLI tool invocations in CI.
# Records command string, version, and tool/MCP configuration.
# Tool name is derived from the first element of LUNAR_CI_COMMAND.

source "$(dirname "$0")/helpers.sh"

CMD_STR=$(parse_cmd_str)
TOOL=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\["//; s/".*$//')
VERSION=$(get_tool_version "$TOOL")

# Extract tool/MCP config flags based on tool type.
# Each tool has its own CLI format — we extract raw values without judgment.
ALLOWED_TOOLS=""
DISALLOWED_TOOLS=""
TOOLS_RESTRICTION=""
MCP_CONFIG=""
SANDBOX=""
APPROVAL_MODE=""

case "$TOOL" in
  claude)
    ALLOWED_TOOLS=$(extract_flag_values "$CMD_STR" "--allowedTools")
    DISALLOWED_TOOLS=$(extract_flag_values "$CMD_STR" "--disallowedTools")
    TOOLS_RESTRICTION=$(extract_flag_value "$CMD_STR" "--tools")
    MCP_CONFIG=$(extract_flag_value "$CMD_STR" "--mcp-config")
    ;;
  codex)
    SANDBOX=$(extract_flag_value "$CMD_STR" "--sandbox" "-s")
    APPROVAL_MODE=$(extract_flag_value "$CMD_STR" "--ask-for-approval" "-a")
    ;;
  gemini)
    SANDBOX=$(extract_flag_value "$CMD_STR" "--sandbox" "-s")
    APPROVAL_MODE=$(extract_flag_value "$CMD_STR" "--approval-mode")
    ;;
esac

# Build JSON — only include non-empty fields
# Using heredoc + sed for native bash (no jq in CI collectors)
JSON="{"
JSON="$JSON\"cmd\": \"$(echo "$CMD_STR" | sed 's/"/\\"/g')\","
JSON="$JSON\"tool\": \"$TOOL\","
JSON="$JSON\"version\": \"$VERSION\""

[ -n "$ALLOWED_TOOLS" ] && JSON="$JSON,\"allowed_tools\": \"$(echo "$ALLOWED_TOOLS" | sed 's/"/\\"/g')\""
[ -n "$DISALLOWED_TOOLS" ] && JSON="$JSON,\"disallowed_tools\": \"$(echo "$DISALLOWED_TOOLS" | sed 's/"/\\"/g')\""
[ -n "$TOOLS_RESTRICTION" ] && JSON="$JSON,\"tools_restriction\": \"$(echo "$TOOLS_RESTRICTION" | sed 's/"/\\"/g')\""
[ -n "$MCP_CONFIG" ] && JSON="$JSON,\"mcp_config\": \"$(echo "$MCP_CONFIG" | sed 's/"/\\"/g')\""
[ -n "$SANDBOX" ] && JSON="$JSON,\"sandbox\": \"$SANDBOX\""
[ -n "$APPROVAL_MODE" ] && JSON="$JSON,\"approval_mode\": \"$APPROVAL_MODE\""

JSON="$JSON}"

echo "[$JSON]" | lunar collect -j ".ai_use.cicd.cmds" -
