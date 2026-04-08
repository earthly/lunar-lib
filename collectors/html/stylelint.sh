#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

if ! is_html_project; then
    echo "No HTML/CSS project detected" >&2
    exit 0
fi

# Check for CSS-family files
css_files=$(find . -maxdepth 10 -type f \( -name "*.css" -o -name "*.scss" -o -name "*.less" \) -not -path './.git/*' -not -path '*/node_modules/*' 2>/dev/null)
if [[ -z "$css_files" ]]; then
    echo "No CSS/SCSS/LESS files found for Stylelint" >&2
    exit 0
fi

# Run Stylelint with JSON output and default config
# Use --config to provide a minimal config if no project config exists
STYLELINT_CONFIG=""
if [[ ! -f ".stylelintrc" ]] && [[ ! -f ".stylelintrc.json" ]] && [[ ! -f ".stylelintrc.yml" ]] && [[ ! -f "stylelint.config.js" ]] && [[ ! -f "stylelint.config.mjs" ]]; then
    STYLELINT_CONFIG='--config {"extends":"stylelint-config-standard"}'
fi

set +e
echo "$css_files" | xargs stylelint --formatter json $STYLELINT_CONFIG > /tmp/stylelint-output.json 2>/dev/null
exit_code=$?
set -e

if [[ ! -f /tmp/stylelint-output.json ]] || [[ ! -s /tmp/stylelint-output.json ]]; then
    echo "Stylelint did not produce output" >&2
    exit 0
fi

# Parse JSON output into normalized warnings
warnings=$(python3 - <<'PY'
import json
import sys

try:
    with open("/tmp/stylelint-output.json") as f:
        data = json.load(f)

    warnings = []
    for file_result in data:
        file_path = file_result.get("source", "")
        for warning in file_result.get("warnings", []):
            warnings.append({
                "file": file_path,
                "line": warning.get("line", 0),
                "severity": warning.get("severity", "warning"),
                "message": warning.get("text", ""),
                "rule": warning.get("rule", "")
            })

    print(json.dumps(warnings))
except Exception as e:
    print("[]", file=sys.stdout)
    print(f"Error parsing Stylelint output: {e}", file=sys.stderr)
PY
)

warning_count=$(echo "$warnings" | jq '[.[] | select(.severity == "warning")] | length')
error_count=$(echo "$warnings" | jq '[.[] | select(.severity == "error")] | length')
total_count=$(echo "$warnings" | jq 'length')
passed=true
if [[ "$total_count" -gt 0 ]]; then
    passed=false
fi

# Collect normalized lint data
echo "$warnings" | jq '{
    warnings: .,
    tool: "stylelint",
    source: { tool: "stylelint", integration: "code" }
}' | lunar collect -j ".lang.css.lint" -

# Collect raw stylelint metadata
jq -n \
    --argjson passed "$passed" \
    --argjson error_count "$error_count" \
    --argjson warning_count "$warning_count" \
    '{
        passed: $passed,
        error_count: $error_count,
        warning_count: $warning_count,
        source: { tool: "stylelint", integration: "code" }
    }' | lunar collect -j ".lang.css.native.stylelint" -
