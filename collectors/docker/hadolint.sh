#!/bin/bash

set -e

# Command to find Dockerfiles (from input or default)
FIND_CMD="${LUNAR_VAR_FIND_COMMAND:-find . -type f \( -name Dockerfile -o -name '*.Dockerfile' -o -name 'Dockerfile.*' \)}"

# Find all Dockerfiles
DOCKERFILES=$(eval "$FIND_CMD" 2>/dev/null | sed 's|^\./||' || true)

if [ -z "$DOCKERFILES" ]; then
    echo "No Dockerfiles found — nothing to lint" >&2
    exit 0
fi

# Get hadolint version
HADOLINT_VERSION=$(cat /usr/local/bin/hadolint.version 2>/dev/null || echo "unknown")

# Run hadolint on all Dockerfiles with JSON output
# Exit code 0 = clean, 1 = issues found, >1 = error
EXIT_CODE=0
RAW_OUTPUT=$(echo "$DOCKERFILES" | xargs hadolint --format json 2>/dev/null) || EXIT_CODE=$?

if [ "$EXIT_CODE" -gt 1 ]; then
    echo "hadolint exited with unexpected code $EXIT_CODE" >&2
    exit 0
fi

# If empty output or null, treat as clean
if [ -z "$RAW_OUTPUT" ] || [ "$RAW_OUTPUT" = "null" ] || [ "$RAW_OUTPUT" = "[]" ]; then
    RAW_OUTPUT="[]"
fi

# Collect raw hadolint output to .containers.native.hadolint
jq -n \
    --arg tool "hadolint" \
    --arg version "$HADOLINT_VERSION" \
    --argjson report "$RAW_OUTPUT" \
    '{
        source: { tool: $tool, version: $version, integration: "auto" },
        report: $report
    }' | lunar collect -j ".containers.native.hadolint" -

# Build normalized lint_results: group issues by file path
# Each entry has { path, issues: [{ line, rule, severity, message }] }
LINT_RESULTS=$(echo "$RAW_OUTPUT" | jq '
    group_by(.file) | map({
        path: (.[0].file | sub("^\\./"; "")),
        issues: [.[] | {
            line: .line,
            rule: .code,
            severity: .level,
            message: .message
        }]
    })
')

# Only collect lint_results if there are actual issues
ISSUE_COUNT=$(echo "$RAW_OUTPUT" | jq 'length')
if [ "$ISSUE_COUNT" -gt 0 ]; then
    echo "$LINT_RESULTS" | lunar collect -j ".containers.lint_results" -
fi
