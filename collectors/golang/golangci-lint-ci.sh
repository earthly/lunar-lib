#!/bin/bash
set -e

# CI collector - runs native on CI runner, avoid jq and heavy dependencies.
#
# Detects user-invoked `golangci-lint run` in CI pipelines. Records the
# command and version. When the user's command produced JSON output (either
# captured on stdout via LUNAR_CI_OUTPUT, or written to a file via
# `--output.json.path=<file>`), parses issues into normalized lint warnings
# at the same path as the code-hook `golangci-lint` sub-collector.

if [ -z "$LUNAR_CI_COMMAND" ]; then
    exit 0
fi

# Parse LUNAR_CI_COMMAND from JSON array into a space-separated string.
CMD_RAW="$LUNAR_CI_COMMAND"
if [[ "$CMD_RAW" == "["* ]]; then
    CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
    CMD_STR="$CMD_RAW"
fi

# Only collect from the `run` subcommand. `golangci-lint version` /
# `golangci-lint linters` / `golangci-lint cache` etc. don't produce lint
# results and would write empty/misleading data.
# Token-walk the args (excluding flags) to find the first positional —
# that's the subcommand in golangci-lint's CLI.
SUBCMD=""
BIN_NAME="${LUNAR_CI_COMMAND_BIN:-golangci-lint}"
for arg in $CMD_STR; do
    case "$arg" in
        -*) continue ;;                  # skip flags
        */"$BIN_NAME"|"$BIN_NAME") continue ;;  # skip the binary path itself
        *)
            SUBCMD="$arg"
            break
            ;;
    esac
done
if [ -n "$SUBCMD" ] && [ "$SUBCMD" != "run" ]; then
    exit 0
fi

# Resolve traced binary for accurate version extraction.
GOLANGCI_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-golangci-lint}"
VERSION=$("$GOLANGCI_BIN" version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+[.0-9]*' | head -1 || echo "")

# If user redirected JSON output to a file (e.g. `--output.json.path=report.json`
# or legacy v1 `--out-format=json:report.json`), capture the file path so we
# can read structured warnings from it. LUNAR_CI_OUTPUT only captures stdout,
# so file outputs need this fallback.
JSON_FILE=""
prev=""
for arg in $CMD_STR; do
    # Modern v2 syntax: --output.json.path=<path> or --output.json.path <path>
    if [[ "$arg" == --output.json.path=* ]]; then
        candidate="${arg#--output.json.path=}"
        if [ "$candidate" != "stdout" ] && [ "$candidate" != "-" ]; then
            JSON_FILE="$candidate"
        fi
    elif [[ "$prev" == "--output.json.path" ]]; then
        if [ "$arg" != "stdout" ] && [ "$arg" != "-" ]; then
            JSON_FILE="$arg"
        fi
    # Legacy v1 syntax: --out-format=json:<path>
    elif [[ "$arg" == --out-format=json:* ]]; then
        candidate="${arg#--out-format=json:}"
        if [ -n "$candidate" ] && [ "$candidate" != "stdout" ]; then
            JSON_FILE="$candidate"
        fi
    fi
    prev="$arg"
done

# Determine the JSON payload to parse: file output beats stdout when both
# are present (file is more reliable — stdout may be polluted by other tools).
JSON_PAYLOAD=""
if [ -n "$JSON_FILE" ] && [ -f "$JSON_FILE" ]; then
    JSON_PAYLOAD=$(cat "$JSON_FILE")
elif [ -n "$LUNAR_CI_OUTPUT" ]; then
    JSON_PAYLOAD="$LUNAR_CI_OUTPUT"
fi

# Try to parse warnings. Requires jq + JSON output with .Issues array.
# Without jq or with non-JSON stdout we still record the passive signal
# below (lint was run, version captured) so the `lint-ran` policy passes.
WARNINGS_JSON="[]"
if [ -n "$JSON_PAYLOAD" ] && command -v jq >/dev/null 2>&1; then
    if echo "$JSON_PAYLOAD" | jq -e '.Issues' >/dev/null 2>&1; then
        WARNINGS_JSON=$(echo "$JSON_PAYLOAD" | jq -c '[.Issues // [] | .[] | {
            file: .Pos.Filename,
            line: .Pos.Line,
            column: .Pos.Column,
            message: .Text,
            linter: .FromLinter
        }]')
    fi
fi

# Helper: JSON-escape a string in pure bash (no jq).
json_escape() {
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/\\t/g' | tr '\n' ' '
}

# Always write normalized lint data with source metadata. Object presence
# at `.lang.go.lint` is what the `lint-ran` policy checks for — even when
# we couldn't parse warnings, recording linters + source makes the policy
# pass and signals that linting was observed in CI.
if command -v jq >/dev/null 2>&1; then
    jq -nc \
      --argjson warnings "$WARNINGS_JSON" \
      --arg version "$VERSION" \
      '{
        warnings: $warnings,
        linters: ["golangci-lint"],
        source: ({
          tool: "golangci-lint",
          integration: "ci"
        } + (if $version != "" then {version: $version} else {} end))
      }' | lunar collect -j ".lang.go.lint" -
else
    # No jq available — write minimal signal without warnings parsing.
    VERSION_FIELD=""
    if [ -n "$VERSION" ]; then
        VERSION_FIELD=",\"version\":\"$VERSION\""
    fi
    echo "{\"linters\":[\"golangci-lint\"],\"source\":{\"tool\":\"golangci-lint\",\"integration\":\"ci\"$VERSION_FIELD}}" \
      | lunar collect -j ".lang.go.lint" -
fi

# Record the CI invocation under native.golangci_lint.cicd for audit trail.
CMD_ESCAPED=$(json_escape "$CMD_STR")
echo "[{\"cmd\":\"$CMD_ESCAPED\",\"version\":\"$VERSION\"}]" \
  | lunar collect -j ".lang.go.native.golangci_lint.cicd.cmds" -
