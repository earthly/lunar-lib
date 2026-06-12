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

# Capture Grype version using the exact traced binary
GRYPE_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-grype}"
GRYPE_VERSION=$("$GRYPE_BIN" version 2>/dev/null | grep -iE 'version:' | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' || echo "unknown")

# Escape quotes in command for JSON
CMD_ESCAPED=$(echo "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

# Write cicd command entry (no jq required)
echo "{\"cmds\":[{\"cmd\":\"$CMD_ESCAPED\",\"version\":\"$GRYPE_VERSION\"}]}" | \
    lunar collect -j ".sca.native.grype.cicd" -

# Write source metadata
lunar collect ".sca.source.tool" "grype"
lunar collect ".sca.source.integration" "ci"
if [ -n "$GRYPE_VERSION" ] && [ "$GRYPE_VERSION" != "unknown" ]; then
    lunar collect ".sca.source.version" "$GRYPE_VERSION"
fi

# Capture raw scan output if Grype wrote to a file we can find.
# Grype output forms: -o json / --output json (stdout), -o json=FILE /
# --output json=FILE (Grype's file syntax), --file FILE, or a shell redirect.
OUTPUT_FORMAT=""
OUTPUT_FILE=""

# 1) -o json / --output json / --output=json (also sarif)
if echo "$CMD_STR" | grep -qE '(-o|--output)[[:space:]=]+(json|sarif)([[:space:]=]|$)'; then
    OUTPUT_FORMAT=$(echo "$CMD_STR" | grep -oE '(-o|--output)[[:space:]=]+(json|sarif)' | head -1 | sed -E 's/(-o|--output)[[:space:]=]+//')
fi

# 2) -o json=FILE / --output json=FILE  (Grype writes the format to a file)
if echo "$CMD_STR" | grep -qE '(-o|--output)[[:space:]=]+(json|sarif)=[^[:space:]]+'; then
    OUTPUT_FILE=$(echo "$CMD_STR" | grep -oE '(-o|--output)[[:space:]=]+(json|sarif)=[^[:space:]]+' | head -1 | sed -E 's/.*=//')
fi

# 3) --file FILE / --file=FILE
if [ -z "$OUTPUT_FILE" ] && echo "$CMD_STR" | grep -qE '\-\-file[[:space:]=]+[^[:space:]]+'; then
    OUTPUT_FILE=$(echo "$CMD_STR" | grep -oE '\-\-file[[:space:]=]+[^[:space:]]+' | head -1 | sed -E 's/--file[[:space:]=]+//')
fi

# 4) Shell redirect: grype ... > file.json
if [ -z "$OUTPUT_FILE" ] && echo "$CMD_STR" | grep -qE '>[[:space:]]*[^[:space:]]+\.(json|sarif)'; then
    OUTPUT_FILE=$(echo "$CMD_STR" | grep -oE '>[[:space:]]*[^[:space:]]+\.(json|sarif)' | head -1 | sed 's/>[[:space:]]*//')
    [ -z "$OUTPUT_FORMAT" ] && OUTPUT_FORMAT="${OUTPUT_FILE##*.}"
fi

RAW_PATH=""
case "$OUTPUT_FORMAT" in
    json)  RAW_PATH=".sca.native.grype.cicd.raw" ;;
    sarif) RAW_PATH=".sca.native.grype.cicd.sarif" ;;
esac

if [ -n "$RAW_PATH" ] && [ -n "$OUTPUT_FILE" ] && [ -f "$OUTPUT_FILE" ]; then
    echo "Collecting raw Grype output from $OUTPUT_FILE (format: $OUTPUT_FORMAT)" >&2
    lunar collect -j "$RAW_PATH" - < "$OUTPUT_FILE" || \
        echo "Warning: Failed to collect raw Grype output from $OUTPUT_FILE" >&2
fi
