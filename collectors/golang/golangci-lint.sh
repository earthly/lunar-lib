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

# Run golangci-lint
set +e
golangci_lint_output=$(golangci-lint run --timeout=5m 2>&1)
golangci_lint_exit_code=$?
set -e

if [[ $golangci_lint_exit_code -eq 0 ]]; then
  golangci_lint_passed=true
fi

# Parse golangci-lint output to extract warnings
# Format is typically: file.go:line:column: message (linter-name)
warnings_json="[]"
if [[ -n "$golangci_lint_output" ]] && [[ $golangci_lint_exit_code -ne 0 ]]; then
  warnings_json=$(echo "$golangci_lint_output" | grep -E '^[^:]+:[0-9]+:[0-9]+:' | while IFS= read -r line || [[ -n "$line" ]]; do
    # Parse line: file.go:line:column: message (linter-name)
    # Extract file path (may contain colons, so we need to be careful)
    file_part=$(echo "$line" | sed -E 's/^([^:]+:[0-9]+:[0-9]+):.*/\1/')
    file=$(echo "$file_part" | cut -d: -f1)
    line_num=$(echo "$file_part" | cut -d: -f2)
    col=$(echo "$file_part" | cut -d: -f3)
    
    # Extract the rest after file:line:column:
    rest=$(echo "$line" | sed -E 's/^[^:]+:[0-9]+:[0-9]+:[[:space:]]*//')
    
    # Extract linter name from parentheses at the end
    linter=$(echo "$rest" | grep -oE '\([^)]+\)$' | tr -d '()' || echo "")
    
    # Extract message (everything except the linter name in parentheses)
    message=$(echo "$rest" | sed -E 's/[[:space:]]*\([^)]+\)$//' || echo "$rest")
    
    jq -n \
      --arg file "$file" \
      --arg line "$line_num" \
      --arg col "$col" \
      --arg message "$message" \
      --arg linter "$linter" \
      '{
        file: $file,
        line: (if $line != "" then ($line | tonumber) else null end),
        column: (if $col != "" then ($col | tonumber) else null end),
        message: $message,
        linter: (if $linter != "" then $linter else null end)
      }'
  done | jq -s '.')
fi

# Collect normalized lint data
jq -n \
  --argjson warnings "$warnings_json" \
  '{
    warnings: $warnings,
    linters: ["golangci-lint"]
  }' | lunar collect -j ".lang.go.lint" -

# Collect tool-specific golangci-lint data
jq -n \
  --argjson passed "$golangci_lint_passed" \
  --argjson config_exists "$golangci_lint_config_exists" \
  --arg output "$golangci_lint_output" \
  --arg exit_code "$golangci_lint_exit_code" \
  '{
    passed: $passed,
    config_exists: $config_exists,
    exit_code: ($exit_code | tonumber),
    output: $output
  }' | lunar collect -j ".lang.go.golangci-lint" -


