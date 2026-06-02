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

# Capture raw scan output if Trivy wrote to a file we can find.
# Trivy supports: -f|--format <fmt> -o|--output <file>, or shell redirect.
OUTPUT_FORMAT=""
OUTPUT_FILE=""

# 1) -f json / --format json (also sarif)
if echo "$CMD_STR" | grep -qE '(-f|--format)[[:space:]]+(json|sarif)([[:space:]]|$)'; then
    OUTPUT_FORMAT=$(echo "$CMD_STR" | grep -oE '(-f|--format)[[:space:]]+(json|sarif)' | head -1 | awk '{print $2}')
fi

# 2) -o <file> / --output <file>
if echo "$CMD_STR" | grep -qE '(-o|--output)[[:space:]]+[^[:space:]]+'; then
    OUTPUT_FILE=$(echo "$CMD_STR" | grep -oE '(-o|--output)[[:space:]]+[^[:space:]]+' | head -1 | awk '{print $2}')
fi

# 3) Shell redirect: trivy ... > file.json
if [ -z "$OUTPUT_FILE" ] && echo "$CMD_STR" | grep -qE '>[[:space:]]*[^[:space:]]+\.(json|sarif)'; then
    OUTPUT_FILE=$(echo "$CMD_STR" | grep -oE '>[[:space:]]*[^[:space:]]+\.(json|sarif)' | head -1 | sed 's/>[[:space:]]*//')
    [ -z "$OUTPUT_FORMAT" ] && OUTPUT_FORMAT="${OUTPUT_FILE##*.}"
fi

RAW_PATH=""
case "$OUTPUT_FORMAT" in
    json)  RAW_PATH=".sca.native.trivy.cicd.raw" ;;
    sarif) RAW_PATH=".sca.native.trivy.cicd.sarif" ;;
esac

if [ -n "$RAW_PATH" ] && [ -n "$OUTPUT_FILE" ] && [ -f "$OUTPUT_FILE" ]; then
    echo "Collecting raw Trivy output from $OUTPUT_FILE (format: $OUTPUT_FORMAT)" >&2
    lunar collect -j "$RAW_PATH" - < "$OUTPUT_FILE" || \
        echo "Warning: Failed to collect raw Trivy output from $OUTPUT_FILE" >&2
fi
