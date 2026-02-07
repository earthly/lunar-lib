#!/bin/bash
set -e

# CI collector - runs native on CI runner, avoid jq and heavy dependencies

# Validate required environment variable
if [ -z "$LUNAR_CI_COMMAND" ]; then
    exit 0
fi

# Get the command that was run
CMD_RAW="$LUNAR_CI_COMMAND"

# Convert JSON array to string if needed (LUNAR_CI_COMMAND may be JSON array)
# Handle both: ["semgrep", "scan"] and "semgrep scan"
if [[ "$CMD_RAW" == "["* ]]; then
    # JSON array - extract elements without jq using sed/tr
    # Remove brackets and quotes, replace commas with spaces
    CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
    CMD_STR="$CMD_RAW"
fi

# Skip if this looks like a git command
if echo "$CMD_STR" | grep -qE '^(/usr/bin/)?git\s'; then
    exit 0
fi

# Verify this command invokes semgrep or pysemgrep (but not semgrep-core which is internal)
if ! echo "$CMD_STR" | grep -qE '(^|/)(semgrep|pysemgrep)(\s|$)'; then
    exit 0
fi

# Skip semgrep-core (internal subprocess)
if echo "$CMD_STR" | grep -qE '(^|/)semgrep-core(\s|$)'; then
    exit 0
fi

# Detect category from command (SCA if --supply-chain flag, otherwise SAST)
CMD_LOWER=$(echo "$CMD_STR" | tr '[:upper:]' '[:lower:]')
if echo "$CMD_LOWER" | grep -qE "(--supply-chain|supply\.chain)"; then
    CATEGORY="sca"
else
    CATEGORY="sast"
fi

# Capture exit code (ensure numeric)
EXIT_CODE="${LUNAR_CI_COMMAND_EXIT_CODE:-0}"
if ! [[ "$EXIT_CODE" =~ ^[0-9]+$ ]]; then
    EXIT_CODE=0
fi

# Capture Semgrep CLI version
SEMGREP_VERSION=$(semgrep --version 2>/dev/null || echo "unknown")

# Sanitize command to redact potential secrets
CMD_SAFE=$(echo "$CMD_STR" | sed -E \
    -e 's/(--auth-token|--token)(=| )[^ ]+/\1=<redacted>/Ig' \
    -e 's/(SEMGREP_APP_TOKEN=)[^ ]+/\1<redacted>/Ig')

# Write results using individual field collection (no jq required)
lunar collect ".$CATEGORY.native.semgrep.cli_command" "$CMD_SAFE"
lunar collect -j ".$CATEGORY.native.semgrep.exit_code" "$EXIT_CODE"
lunar collect ".$CATEGORY.native.semgrep.cli_version" "$SEMGREP_VERSION"

# Write source metadata
lunar collect ".$CATEGORY.source.tool" "semgrep"
lunar collect ".$CATEGORY.source.integration" "ci"
if [ -n "$SEMGREP_VERSION" ] && [ "$SEMGREP_VERSION" != "unknown" ]; then
    lunar collect ".$CATEGORY.source.version" "$SEMGREP_VERSION"
fi
