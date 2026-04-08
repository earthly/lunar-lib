#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

if ! is_html_project; then
    echo "No HTML/CSS project detected" >&2
    exit 0
fi

# Check for HTML files specifically
html_files=$(find . -maxdepth 10 -type f -name "*.html" -not -path './.git/*' -not -path '*/node_modules/*' 2>/dev/null)
if [[ -z "$html_files" ]]; then
    echo "No .html files found for HTMLHint" >&2
    exit 0
fi

# Run HTMLHint with JSON output
set +e
echo "$html_files" | xargs htmlhint --format json > /tmp/htmlhint-output.json 2>/dev/null
exit_code=$?
set -e

if [[ ! -f /tmp/htmlhint-output.json ]] || [[ ! -s /tmp/htmlhint-output.json ]]; then
    echo "HTMLHint did not produce output" >&2
    exit 0
fi

# Parse JSON output into normalized warnings
warnings=$(python3 - <<'PY'
import json
import sys

try:
    with open("/tmp/htmlhint-output.json") as f:
        data = json.load(f)

    warnings = []
    for file_result in data:
        file_path = file_result.get("file", "")
        for msg in file_result.get("messages", []):
            warnings.append({
                "file": file_path,
                "line": msg.get("line", 0),
                "severity": msg.get("type", "warning"),
                "message": msg.get("message", ""),
                "rule": msg.get("rule", {}).get("id", "") if isinstance(msg.get("rule"), dict) else str(msg.get("rule", ""))
            })

    print(json.dumps(warnings))
except Exception as e:
    print("[]", file=sys.stdout)
    print(f"Error parsing HTMLHint output: {e}", file=sys.stderr)
PY
)

warning_count=$(echo "$warnings" | jq 'length')
error_count=$(echo "$warnings" | jq '[.[] | select(.severity == "error")] | length')
passed=true
if [[ "$warning_count" -gt 0 ]]; then
    passed=false
fi

# Collect normalized lint data
echo "$warnings" | jq '{
    warnings: .,
    tool: "htmlhint",
    source: { tool: "htmlhint", integration: "code" }
}' | lunar collect -j ".lang.html.lint" -

# Collect raw htmlhint metadata
jq -n \
    --argjson passed "$passed" \
    --argjson error_count "$error_count" \
    --argjson warning_count "$warning_count" \
    '{
        passed: $passed,
        error_count: $error_count,
        warning_count: $warning_count,
        source: { tool: "htmlhint", integration: "code" }
    }' | lunar collect -j ".lang.html.native.htmlhint" -
