#!/bin/bash

set -e

source "$(dirname "$0")/helpers.sh"

# Run golangci-lint and collect results under .lang.go.lint (normalized) and .lang.go.golangci-lint (tool-specific)

# Check if this is a Go project
if ! is_go_project; then
    echo "No Go project detected, exiting"
    exit 0
fi

golangci_lint_passed=false
golangci_lint_output=""
golangci_lint_config_exists=false

# Check for golangci-lint config
if [[ -f ".golangci.yml" ]] || [[ -f ".golangci.yaml" ]] || [[ -f "golangci.yml" ]] || [[ -f "golangci.yaml" ]]; then
  golangci_lint_config_exists=true
fi

# Get timeout from input (defaults to 10m for slower environments)
LINT_TIMEOUT="${LINT_TIMEOUT:-10m}"

# Ensure Go modules are downloaded first 
# (avoids timeout during package loading during golangci-lint run)
go mod download 2>/dev/null || true

# Run golangci-lint with JSON output for reliable parsing
# --show-stats=false disables the human-readable summary that would otherwise be mixed with JSON
set +e
golangci_lint_json=$(golangci-lint run --timeout="$LINT_TIMEOUT" --output.json.path stdout --show-stats=false 2>/tmp/stderr)
golangci_lint_exit_code=$?
golangci_lint_errors=$(cat /tmp/stderr)
set -e

if [[ $golangci_lint_exit_code -eq 0 ]]; then
  golangci_lint_passed=true
fi

# Parse JSON output to extract warnings
# golangci-lint JSON format has an "Issues" array with objects containing:
# Pos.Filename, Pos.Line, Pos.Column, Text, FromLinter
warnings_json="[]"
if [[ -n "$golangci_lint_json" ]] && echo "$golangci_lint_json" | jq -e '.Issues' >/dev/null 2>&1; then
  warnings_json=$(echo "$golangci_lint_json" | jq '[.Issues // [] | .[] | {
    file: .Pos.Filename,
    line: .Pos.Line,
    column: .Pos.Column,
    message: .Text,
    linter: .FromLinter
  }]')
fi

# Store the text output for human readability
# Extract formatted issues from JSON, or preserve raw output if golangci-lint failed
if echo "$golangci_lint_json" | jq -e '.Issues' >/dev/null 2>&1; then
  golangci_lint_output=$(echo "$golangci_lint_json" | jq -r '
    [.Issues[] | "\(.Pos.Filename):\(.Pos.Line):\(.Pos.Column): \(.Text) (\(.FromLinter))"] | join("\n")
  ')
  # Append any stderr errors (e.g., timeout warnings)
  if [[ -n "$golangci_lint_errors" ]]; then
    golangci_lint_output="${golangci_lint_output}"$'\n'"${golangci_lint_errors}"
  fi
else
  # Preserve error output when golangci-lint fails (e.g., exit code 3)
  golangci_lint_output="$golangci_lint_errors"
fi

# Collect normalized lint data with source metadata
jq -n \
  --argjson warnings "$warnings_json" \
  '{
    warnings: $warnings,
    linters: ["golangci-lint"],
    source: {
      tool: "golangci-lint",
      integration: "code"
    }
  }' | lunar collect -j ".lang.go.lint" -

# Collect tool-specific golangci-lint data
jq -n \
  --argjson passed "$golangci_lint_passed" \
  --argjson config_exists "$golangci_lint_config_exists" \
  --arg output "$golangci_lint_output" \
  --argjson exit_code "$golangci_lint_exit_code" \
  '{
    passed: $passed,
    config_exists: $config_exists,
    exit_code: $exit_code,
    output: $output
  }' | lunar collect -j ".lang.go.golangci_lint" -
