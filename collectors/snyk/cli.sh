#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Validate required environment variable
if [ -z "$LUNAR_CI_COMMAND" ]; then
    echo "LUNAR_CI_COMMAND is not set, skipping." >&2
    exit 0
fi

# Get the command that was run
CMD_RAW="$LUNAR_CI_COMMAND"

# Handle LUNAR_CI_COMMAND as JSON array or string
# Snyk can be invoked as:
#   - snyk test ...
#   - snyk code test ...
#   - /path/to/snyk container test ...
#   - npx snyk ...
# We want to capture snyk but NOT git commands with "snyk" in branch name
CMD_STR=$(echo "$CMD_RAW" | jq -r 'if type == "array" then join(" ") else . end' 2>/dev/null || echo "$CMD_RAW")

# Skip if this looks like a git command (git commands won't have snyk as a path component)
if echo "$CMD_STR" | grep -qE '^(\[?"/usr/bin/git|git\s)'; then
    exit 0
fi

# Verify this command invokes snyk (but not just mentions it in a path or arg)
if ! echo "$CMD_STR" | grep -qE '(^|/|npx )snyk(\s|$|")'; then
    exit 0
fi

# Detect category from command
CATEGORY=$(detect_snyk_category_from_cmd "$CMD_STR")

# Capture exit code from the command
EXIT_CODE="${LUNAR_CI_COMMAND_EXIT_CODE:-0}"

# Capture Snyk CLI version
SNYK_VERSION=$(snyk --version 2>/dev/null || echo "unknown")

# Sanitize command to redact potential secrets (tokens, credentials)
CMD_SAFE=$(echo "$CMD_STR" | sed -E \
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
