#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Check if this is a Go project
if ! is_go_project; then
    echo "No Go project detected, exiting"
    exit 0
fi

# CI collector - runs native on CI runner, avoid jq and heavy dependencies

# Convert LUNAR_CI_COMMAND from JSON array to string if needed
CMD_RAW="$LUNAR_CI_COMMAND"
if [[ "$CMD_RAW" == "["* ]]; then
    CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
    CMD_STR="$CMD_RAW"
fi

# Determine test scope based on command arguments
if echo "$CMD_STR" | grep -q '\./\.\.\.'; then
    scope="recursive"
else
    scope="package"
fi

# Collect Go-specific test scope with source metadata
lunar collect ".lang.go.tests.scope" "$scope" \
             ".lang.go.tests.source.tool" "go" \
             ".lang.go.tests.source.integration" "ci"

# Collect normalized indicator that tests were executed (presence of .testing signals this)
# Other collectors (e.g., JUnit XML parser) can populate detailed fields like:
#   .testing.results (total, passed, failed, skipped)
#   .testing.failures (individual test failure details)
#   .testing.all_passing (boolean summary)
lunar collect ".testing.source.tool" "go test" \
             ".testing.source.integration" "ci"
