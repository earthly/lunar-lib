#!/bin/bash
set -e

# Extract coverage from existing test output (native — no jq)
# This runs AFTER the test command completes — do NOT re-run tests.

# Look for coverage output in known locations
COVERAGE_FILE=""
for candidate in \
    "coverage/coverage-summary.json" \
    "coverage/coverage-final.json"; do
    if [[ -f "$candidate" ]]; then
        COVERAGE_FILE="$candidate"
        break
    fi
done

if [[ -z "$COVERAGE_FILE" ]]; then
    echo "No coverage output found, exiting"
    exit 0
fi

# Extract total line coverage percentage from coverage-summary.json
# Format: {"total":{"lines":{"total":N,"covered":N,"skipped":N,"pct":85.5},...}}
coverage_pct=""
if [[ "$COVERAGE_FILE" == *"coverage-summary.json"* ]]; then
    # Extract pct from total.lines using grep/sed (native, no jq)
    coverage_pct=$(grep -o '"lines":{[^}]*}' "$COVERAGE_FILE" | head -1 | grep -o '"pct":[0-9.]*' | sed 's/"pct"://')
fi

# Fallback: try coverage-final.json — compute from hit/miss counts
if [[ -z "$coverage_pct" ]] && [[ "$COVERAGE_FILE" == *"coverage-final.json"* ]]; then
    # coverage-final.json has per-file statement maps; skip complex parsing
    echo "coverage-final.json found but summary extraction not supported, exiting"
    exit 0
fi

if [[ -z "$coverage_pct" ]]; then
    echo "Could not extract coverage percentage from $COVERAGE_FILE"
    exit 0
fi

# Determine the test tool from the command
CMD_STR=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
tool="jest"
case "$CMD_STR" in
    *vitest*) tool="vitest" ;;
    *nyc*)    tool="nyc" ;;
    *c8*)     tool="c8" ;;
esac

# Write to language-specific path
lunar collect -j ".lang.nodejs.tests.coverage" "{\"percentage\": $coverage_pct, \"source\": {\"tool\": \"$tool\", \"integration\": \"ci\"}}"

# Dual-write to normalized .testing path
lunar collect -j ".testing.coverage" "{\"percentage\": $coverage_pct}"
lunar collect -j ".testing.source" "{\"tool\": \"$tool\", \"integration\": \"ci\"}"
