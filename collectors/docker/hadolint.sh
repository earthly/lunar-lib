#!/bin/bash

set -e

# Command to find Dockerfiles (from input or default)
FIND_CMD="${LUNAR_VAR_FIND_COMMAND:-find . -type f \( -name Dockerfile -o -name '*.Dockerfile' -o -name 'Dockerfile.*' \)}"

# Find all Dockerfiles
DOCKERFILES=$(eval "$FIND_CMD" 2>/dev/null | sed 's|^\./||' || true)

if [ -z "$DOCKERFILES" ]; then
    echo "No Dockerfiles found — nothing to lint" >&2
    echo "[]" | lunar collect -j ".containers.lint_results" -
    exit 0
fi

# Get hadolint version
HADOLINT_VERSION=$(cat /usr/local/bin/hadolint.version 2>/dev/null || echo "unknown")

# Run hadolint on all Dockerfiles with JSON output
# Exit code 0 = clean, 1 = issues found, >1 = error
# xargs returns 123 when the child exits 1-125, so 123 is also normal.
EXIT_CODE=0
RAW_OUTPUT=$(echo "$DOCKERFILES" | tr '\n' '\0' | xargs -0 hadolint --format json 2>/dev/null) || EXIT_CODE=$?

if [ "$EXIT_CODE" -gt 1 ] && [ "$EXIT_CODE" -ne 123 ]; then
    echo "hadolint exited with unexpected code $EXIT_CODE" >&2
    jq -n --arg code "$EXIT_CODE" \
        '{source: {tool: "hadolint", integration: "auto"}, error: "hadolint exited unexpectedly", exit_code: ($code | tonumber)}' \
        | lunar collect -j ".containers.native.hadolint" -
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

# Always collect lint_results — even when empty — so the policy can
# distinguish "ran clean" (pass) from "never ran" (pending).
echo "$LINT_RESULTS" | lunar collect -j ".containers.lint_results" -
