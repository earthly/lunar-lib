#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

if ! is_rust_project; then
    echo "No Rust project detected, exiting"
    exit 0
fi

if [[ ! -f "Cargo.toml" ]]; then
    echo "No Cargo.toml found, exiting"
    exit 0
fi

clippy_passed=false

# Get optional extra args
CLIPPY_ARGS="${LUNAR_INPUT_clippy_args:-}"

# Run clippy with JSON message format
set +e
clippy_output=$(cargo clippy --message-format=json $CLIPPY_ARGS 2>/tmp/clippy-stderr)
clippy_exit_code=$?
set -e

if [[ $clippy_exit_code -eq 0 ]]; then
    clippy_passed=true
fi

# Parse JSON lines for compiler warnings
# clippy outputs one JSON object per line; filter for compiler-message with warning level
warnings_json=$(echo "$clippy_output" | \
    jq -c 'select(.reason == "compiler-message") | .message | select(.level == "warning")' 2>/dev/null | \
    jq -s '[.[] | {
        file: (.spans[0].file_name // "unknown"),
        line: (.spans[0].line_start // 0),
        column: (.spans[0].column_start // 0),
        message: .message,
        lint: (.code.code // "unknown")
    }]' 2>/dev/null || echo '[]')

# Collect normalized lint data with passed status
jq -n \
    --argjson passed "$clippy_passed" \
    --argjson warnings "$warnings_json" \
    '{
        passed: $passed,
        warnings: $warnings,
        linters: ["clippy"],
        source: {
            tool: "clippy",
            integration: "code"
        }
    }' | lunar collect -j ".lang.rust.lint" -
