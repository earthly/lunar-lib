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
# Handle both: ["snyk", "test"] and "snyk test"
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

# Verify this command invokes snyk (but not just mentions it in a path or arg)
if ! echo "$CMD_STR" | grep -qE '(^|/|npx )snyk(\s|$)'; then
    exit 0
fi

# Detect category from command
CMD_LOWER=$(echo "$CMD_STR" | tr '[:upper:]' '[:lower:]')
if echo "$CMD_LOWER" | grep -q "snyk iac"; then
    CATEGORY="iac_scan"
elif echo "$CMD_LOWER" | grep -q "snyk container"; then
    CATEGORY="container_scan"
elif echo "$CMD_LOWER" | grep -q "snyk code"; then
    CATEGORY="sast"
else
    CATEGORY="sca"  # Default: snyk test = Open Source
fi

# Capture Snyk CLI version
SNYK_VERSION=$(snyk --version 2>/dev/null || echo "unknown")

# Sanitize command to redact potential secrets (tokens, credentials)
CMD_SAFE=$(echo "$CMD_STR" | sed -E \
    -e 's/(snyk auth) [^ ]+/\1 <redacted>/I' \
    -e 's/(--client-id|--client-secret|--token|--auth-token)(=| )[^ ]+/\1=<redacted>/Ig' \
    -e 's/(SNYK_TOKEN|SNYK_OAUTH_TOKEN)=[^ ]+/\1=<redacted>/Ig')

# Escape quotes in command for JSON
CMD_ESCAPED=$(echo "$CMD_SAFE" | sed 's/"/\\"/g')

# Write cicd command entry (no jq required)
# Note: multiple snyk commands in same CI run will each add to this structure
echo "{\"cmds\":[{\"cmd\":\"$CMD_ESCAPED\",\"version\":\"$SNYK_VERSION\"}]}" | \
    lunar collect -j ".$CATEGORY.native.snyk.cicd" -

# Write source metadata
lunar collect ".$CATEGORY.source.tool" "snyk"
lunar collect ".$CATEGORY.source.integration" "ci"
if [ -n "$SNYK_VERSION" ] && [ "$SNYK_VERSION" != "unknown" ]; then
    lunar collect ".$CATEGORY.source.version" "$SNYK_VERSION"
fi
