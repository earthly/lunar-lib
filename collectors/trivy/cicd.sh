#!/bin/bash
set -e

# CI collector - runs native on CI runner, avoid jq and heavy dependencies

# Validate required environment variable
if [ -z "$LUNAR_CI_COMMAND" ]; then
    exit 0
fi

# Convert JSON array to string if needed
CMD_RAW="$LUNAR_CI_COMMAND"
if [[ "$CMD_RAW" == "["* ]]; then
    CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
    CMD_STR="$CMD_RAW"
fi

# Capture Trivy version using the exact traced binary
TRIVY_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-trivy}"
TRIVY_VERSION=$("$TRIVY_BIN" version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' || echo "unknown")

# Escape quotes in command for JSON
CMD_ESCAPED=$(echo "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

# Write cicd command entry (no jq required)
echo "{\"cmds\":[{\"cmd\":\"$CMD_ESCAPED\",\"version\":\"$TRIVY_VERSION\"}]}" | \
    lunar collect -j ".sca.native.trivy.cicd" -

# Write source metadata
lunar collect ".sca.source.tool" "trivy"
lunar collect ".sca.source.integration" "ci"
if [ -n "$TRIVY_VERSION" ] && [ "$TRIVY_VERSION" != "unknown" ]; then
    lunar collect ".sca.source.version" "$TRIVY_VERSION"
fi
