#!/bin/bash
set -e

# Check if this is actually a Go project by looking for .go files
if ! find . -name "*.go" -type f 2>/dev/null | grep -q .; then
    echo "No Go files found, exiting"
    exit 0
fi

# Determine test scope based on command arguments
argument="./..."
if echo "$LUNAR_CI_COMMAND" | jq -e --arg val "$argument" 'index($val) != null' >/dev/null 2>&1; then
    scope="recursive"
else
    scope="package"
fi

# Collect Go-specific test scope with source metadata
jq -n --arg scope "$scope" '{
    scope: $scope,
    source: {
        tool: "go",
        integration: "ci"
    }
}' | lunar collect -j .lang.go.tests -

# Collect normalized indicator that tests were executed (presence of .testing signals this)
# Other collectors (e.g., JUnit XML parser) can populate detailed fields like:
#   .testing.results (total, passed, failed, skipped)
#   .testing.failures (individual test failure details)
#   .testing.all_passing (boolean summary)
jq -n '{
    source: {
        tool: "go test",
        integration: "ci"
    }
}' | lunar collect -j .testing -
