#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Get the command that was run
CMD_RAW="$LUNAR_CI_COMMAND"

# Detect category from command
CATEGORY=$(detect_snyk_category_from_cmd "$CMD_RAW")

# Capture exit code from the command
EXIT_CODE="${LUNAR_CI_COMMAND_EXIT_CODE:-0}"

# Sanitize command to redact potential secrets (tokens, credentials)
CMD_SAFE=$(echo "$CMD_RAW" | sed -E \
    -e 's/(snyk auth) [^ ]+/\1 <redacted>/I' \
    -e 's/(--client-id|--client-secret|--token|--auth-token)(=| )[^ ]+/\1=<redacted>/Ig')

# Write results
jq -n \
    --arg cmd "$CMD_SAFE" \
    --argjson exit_code "$EXIT_CODE" \
    '{cli_command: $cmd, exit_code: $exit_code}' | \
    lunar collect -j ".$CATEGORY.native.snyk" -

write_snyk_source "$CATEGORY" "ci"
