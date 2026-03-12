#!/bin/bash
set -e

# CI collector - runs native on CI runner, avoid jq and heavy dependencies

# Validate required environment variable
if [ -z "$LUNAR_CI_COMMAND" ]; then
  exit 0
fi

# Get the command that was run
CMD_RAW="$LUNAR_CI_COMMAND"

# Convert JSON array to string if needed
if [[ "$CMD_RAW" == "["* ]]; then
  CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
  CMD_STR="$CMD_RAW"
fi

# Verify this command invokes gitleaks
if ! echo "$CMD_STR" | grep -qE '(^|/)gitleaks(\s|$)'; then
  exit 0
fi

# Capture gitleaks CLI version using the exact traced binary
GITLEAKS_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-gitleaks}"
GITLEAKS_VERSION=$("$GITLEAKS_BIN" version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' || echo "unknown")

# Sanitize command to redact potential secrets
CMD_SAFE=$(echo "$CMD_STR" | sed -E \
  -e 's/(--token)(=| )[^ ]+/\1=<redacted>/Ig')

# Escape quotes in command for JSON
CMD_ESCAPED=$(echo "$CMD_SAFE" | sed 's/"/\\"/g')

# Write cicd command entry (no jq required)
echo "{\"cmds\":[{\"cmd\":\"$CMD_ESCAPED\",\"version\":\"$GITLEAKS_VERSION\"}]}" | \
  lunar collect -j ".secrets.native.gitleaks.cicd" -

# Write source metadata
lunar collect ".secrets.source.tool" "gitleaks"
lunar collect ".secrets.source.integration" "ci"
if [ -n "$GITLEAKS_VERSION" ] && [ "$GITLEAKS_VERSION" != "unknown" ]; then
  lunar collect ".secrets.source.version" "$GITLEAKS_VERSION"
fi
