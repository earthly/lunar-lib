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

# Check if this is a semgrep command by looking at all arguments, not just the first
# Semgrep can be invoked as:
#   - semgrep scan ...
#   - python3 /path/to/semgrep scan ...
#   - /path/to/pysemgrep scan ...
#   - semgrep-core ... (internal, skip)
# We want to capture semgrep or pysemgrep but NOT git commands with "semgrep" in branch name
CMD_STR=$(echo "$CMD_RAW" | jq -r 'if type == "array" then join(" ") else . end' 2>/dev/null || echo "$CMD_RAW")

# Skip if this looks like a git command (git commands won't have semgrep/pysemgrep as a path component)
if echo "$CMD_STR" | grep -qE '^(\[?"/usr/bin/git|git\s)'; then
    exit 0
fi

# Verify this command invokes semgrep or pysemgrep (but not semgrep-core which is internal)
if ! echo "$CMD_STR" | grep -qE '(^|/)(semgrep|pysemgrep)(\s|$|")'; then
    exit 0
fi

# Skip semgrep-core (internal subprocess, not the main CLI invocation)
if echo "$CMD_STR" | grep -qE '(^|/)semgrep-core(\s|$|")'; then
    exit 0
fi

# Detect category from command
CATEGORY=$(detect_semgrep_category_from_cmd "$CMD_RAW")

# Capture exit code from the command
EXIT_CODE="${LUNAR_CI_COMMAND_EXIT_CODE:-0}"
# Ensure exit code is numeric (jq --argjson requires valid JSON number)
if ! [[ "$EXIT_CODE" =~ ^[0-9]+$ ]]; then
    EXIT_CODE=0
fi

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
