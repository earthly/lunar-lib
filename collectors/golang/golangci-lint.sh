#!/bin/bash

set -e

# Run golangci-lint and collect results under .lang.go.lint (normalized) and .lang.go.golangci-lint (tool-specific)

# Check if this is actually a Go project by looking for .go files
if ! find . -name "*.go" -type f 2>/dev/null | grep -q .; then
    echo "No Go files found, exiting"
    exit 0
fi

golangci_lint_passed=false
golangci_lint_output=""
golangci_lint_config_exists=false

# Check for golangci-lint config
if [[ -f ".golangci.yml" ]] || [[ -f ".golangci.yaml" ]] || [[ -f "golangci.yml" ]] || [[ -f "golangci.yaml" ]]; then
  golangci_lint_config_exists=true
fi

# Get timeout from input (defaults to 5m)
LINT_TIMEOUT="${LINT_TIMEOUT:-5m}"

# Run golangci-lint with JSON output for reliable parsing
set +e
golangci_lint_json=$(golangci-lint run --timeout="$LINT_TIMEOUT" --out-format=json 2>&1)
golangci_lint_exit_code=$?
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

# Store the text output for human readability (re-run with text format or extract from JSON)
# We'll store a summary from the JSON for the output field
golangci_lint_output=$(echo "$golangci_lint_json" | jq -r '
  if .Issues then
    [.Issues[] | "\(.Pos.Filename):\(.Pos.Line):\(.Pos.Column): \(.Text) (\(.FromLinter))"] | join("\n")
  else
    ""
  end
' 2>/dev/null || echo "")

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
  }' | lunar collect -j ".lang.go.native.golangci_lint" -
