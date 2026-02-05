#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Get the command that was run
CMD_RAW="$LUNAR_CI_COMMAND"

# Detect category from command
CATEGORY=$(detect_snyk_category_from_cmd "$CMD_RAW")

# Capture exit code from the command
EXIT_CODE="${LUNAR_CI_COMMAND_EXIT_CODE:-0}"

# Capture Snyk CLI version
SNYK_VERSION=$(snyk --version 2>/dev/null || echo "unknown")

# Sanitize command to redact potential secrets (tokens, credentials)
CMD_SAFE=$(echo "$CMD_RAW" | sed -E \
    -e 's/(snyk auth) [^ ]+/\1 <redacted>/I' \
    -e 's/(--client-id|--client-secret|--token|--auth-token)(=| )[^ ]+/\1=<redacted>/Ig' \
    -e 's/(^|[[:space:]])(SNYK_TOKEN|SNYK_OAUTH_TOKEN)=[^[:space:]]+/\1\2=<redacted>/Ig')

# Write results
jq -n \
    --arg cmd "$CMD_SAFE" \
    --argjson exit_code "$EXIT_CODE" \
    --arg version "$SNYK_VERSION" \
    '{cli_command: $cmd, exit_code: $exit_code, cli_version: $version}' | \
    lunar collect -j ".$CATEGORY.native.snyk" -

write_snyk_source "$CATEGORY" "ci" "$SNYK_VERSION"
