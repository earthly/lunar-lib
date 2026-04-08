#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

if ! is_html_project; then
    echo "No HTML/CSS project detected" >&2
    exit 0
fi

# Find CSS files (plain CSS only for reliable linting — SCSS/LESS need custom syntaxes)
css_files=$(find . -maxdepth 10 -type f -name "*.css" -not -path './.git/*' -not -path '*/node_modules/*' 2>/dev/null)
scss_files=$(find . -maxdepth 10 -type f -name "*.scss" -not -path './.git/*' -not -path '*/node_modules/*' 2>/dev/null)
less_files=$(find . -maxdepth 10 -type f -name "*.less" -not -path './.git/*' -not -path '*/node_modules/*' 2>/dev/null)

all_files="${css_files}${scss_files:+$'\n'$scss_files}${less_files:+$'\n'$less_files}"
all_files=$(echo "$all_files" | sed '/^$/d')

if [[ -z "$all_files" ]]; then
    echo "No CSS/SCSS/LESS files found for Stylelint" >&2
    exit 0
fi

# Determine if a project config exists
HAS_PROJECT_CONFIG=false
for cfg in .stylelintrc .stylelintrc.json .stylelintrc.yml stylelint.config.js stylelint.config.mjs; do
    if [[ -f "$cfg" ]]; then
        HAS_PROJECT_CONFIG=true
        break
    fi
done

# Run Stylelint per file type to handle syntax differences
> /tmp/stylelint-output.json.parts

run_stylelint() {
    local files="$1"
    local syntax_arg="$2"
    local config_arg="$3"

    [[ -z "$files" ]] && return

    local args=(--formatter json)
    [[ -n "$syntax_arg" ]] && args+=(--custom-syntax "$syntax_arg")
    if [[ "$HAS_PROJECT_CONFIG" == "false" && -n "$config_arg" ]]; then
        args+=(--config "$config_arg")
    fi

    set +e
    echo "$files" | xargs stylelint "${args[@]}" >> /tmp/stylelint-output.json.parts 2>/dev/null
    set -e
}

# CSS: uses default parser with stylelint-config-standard
run_stylelint "$css_files" "" '{"extends":"stylelint-config-standard"}'

# SCSS: uses postcss-scss syntax
run_stylelint "$scss_files" "postcss-scss" '{"extends":"stylelint-config-standard"}'

# LESS: uses postcss-less syntax
run_stylelint "$less_files" "postcss-less" '{"extends":"stylelint-config-standard"}'

# Merge all JSON arrays from the parts file into one array
# Each stylelint run outputs a JSON array; merge them
python3 - <<'PY' > /tmp/stylelint-output.json
import json, sys

results = []
raw = open("/tmp/stylelint-output.json.parts").read().strip()
if not raw:
    print("[]")
    sys.exit(0)

# Each stylelint run appends a JSON array; try to parse them
decoder = json.JSONDecoder()
pos = 0
while pos < len(raw):
    # Skip whitespace
    while pos < len(raw) and raw[pos] in ' \t\n\r':
        pos += 1
    if pos >= len(raw):
        break
    try:
        obj, end = decoder.raw_decode(raw, pos)
        if isinstance(obj, list):
            results.extend(obj)
        pos = end
    except json.JSONDecodeError:
        pos += 1

print(json.dumps(results))
PY

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
