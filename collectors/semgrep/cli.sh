#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Get the command that was run
CMD_RAW="$LUNAR_CI_COMMAND"

# Detect category from command
CATEGORY=$(detect_semgrep_category_from_cmd "$CMD_RAW")

# Capture exit code from the command
EXIT_CODE="${LUNAR_CI_COMMAND_EXIT_CODE:-0}"

# Capture Semgrep CLI version
SEMGREP_VERSION=$(semgrep --version 2>/dev/null || echo "unknown")

# Sanitize command to redact potential secrets (tokens, credentials)
CMD_SAFE=$(echo "$CMD_RAW" | sed -E \
    -e 's/(--auth-token|--token)(=| )[^ ]+/\1=<redacted>/Ig' \
    -e 's/(SEMGREP_APP_TOKEN=)[^ ]+/\1<redacted>/Ig')

# Write results
jq -n \
    --arg cmd "$CMD_SAFE" \
    --argjson exit_code "$EXIT_CODE" \
    --arg version "$SEMGREP_VERSION" \
    '{cli_command: $cmd, exit_code: $exit_code, cli_version: $version}' | \
    lunar collect -j ".$CATEGORY.native.semgrep" -

write_semgrep_source "$CATEGORY" "ci" "$SEMGREP_VERSION"
