#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

if ! is_shell_project; then
    echo "No shell scripts detected" >&2
    exit 0
fi

# Collect scripts
scripts=()
while IFS= read -r f; do
    [[ -n "$f" ]] && scripts+=("$f")
done < <(get_shell_scripts)

if [[ ${#scripts[@]} -eq 0 ]]; then
    echo "No shell scripts found" >&2
    exit 0
fi

# Determine severity level
severity="${LUNAR_INPUT_SHELLCHECK_SEVERITY:-style}"

# Get shellcheck version
sc_version=$(shellcheck --version 2>/dev/null | sed -n 's/^version: //p' || echo "unknown")

# Run shellcheck with JSON output on all scripts
set +e
sc_output=$(shellcheck -f json -S "$severity" "${scripts[@]}" 2>/dev/null)
sc_exit=$?
set -e

# Parse results — shellcheck outputs a JSON array
if [[ -z "$sc_output" ]] || [[ "$sc_output" == "[]" ]]; then
    sc_output="[]"
fi

# Count findings by severity and build normalized warnings
results=$(python3 - "$sc_output" <<'PY'
import json
import sys

raw = sys.argv[1] if len(sys.argv) > 1 else "[]"
try:
    findings = json.loads(raw)
except (json.JSONDecodeError, TypeError):
    findings = []

error_count = 0
warning_count = 0
info_count = 0
style_count = 0
warnings = []

for f in findings:
    level = f.get("level", "")
    if level == "error":
        error_count += 1
    elif level == "warning":
        warning_count += 1
    elif level == "info":
        info_count += 1
    elif level == "style":
        style_count += 1

    warnings.append({
        "file": f.get("file", ""),
        "line": f.get("line", 0),
        "column": f.get("column", 0),
        "message": f.get("message", ""),
        "linter": "shellcheck",
        "severity": level,
        "code": "SC" + str(f.get("code", ""))
    })

total = error_count + warning_count + info_count + style_count
result = {
    "passed": total == 0,
    "error_count": error_count,
    "warning_count": warning_count,
    "info_count": info_count,
    "style_count": style_count,
    "warnings": warnings
}
print(json.dumps(result))
PY
)

files_checked=${#scripts[@]}
passed=$(echo "$results" | jq -r '.passed')
error_count=$(echo "$results" | jq -r '.error_count')
warning_count=$(echo "$results" | jq -r '.warning_count')
info_count=$(echo "$results" | jq -r '.info_count')
style_count=$(echo "$results" | jq -r '.style_count')

# Collect normalized lint data
echo "$results" | jq '{
    warnings: .warnings,
    linters: ["shellcheck"],
    source: { tool: "shellcheck", integration: "code" }
}' | lunar collect -j ".lang.shell.lint" -

# Collect native shellcheck metadata
jq -n \
    --argjson passed "$passed" \
    --arg version "$sc_version" \
    --argjson files_checked "$files_checked" \
    --argjson error_count "$error_count" \
    --argjson warning_count "$warning_count" \
    --argjson info_count "$info_count" \
    --argjson style_count "$style_count" \
    '{
        passed: $passed,
        version: $version,
        files_checked: $files_checked,
        error_count: $error_count,
        warning_count: $warning_count,
        info_count: $info_count,
        style_count: $style_count,
        source: { tool: "shellcheck", integration: "code" }
    }' | lunar collect -j ".lang.shell.native.shellcheck" -
