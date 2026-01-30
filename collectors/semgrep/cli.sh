#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Get the command that was run
CMD=$(echo "$LUNAR_CI_COMMAND" | jq -r '. | join(" ")' 2>/dev/null || echo "$LUNAR_CI_COMMAND")

# Detect category from command
CATEGORY=$(detect_semgrep_category_from_cmd "$CMD")

# Capture exit code from the command
EXIT_CODE="${LUNAR_CI_COMMAND_EXIT_CODE:-0}"

# Write results
jq -n \
    --arg cmd "$CMD" \
    --argjson exit_code "$EXIT_CODE" \
    '{cli_command: $cmd, exit_code: $exit_code}' | \
    lunar collect -j ".$CATEGORY.native.semgrep" -

jq -n '{tool: "semgrep", integration: "ci"}' | \
    lunar collect -j ".$CATEGORY.source" -
