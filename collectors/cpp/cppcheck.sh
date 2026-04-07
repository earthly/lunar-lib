#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

if ! is_cpp_project; then
    echo "No C/C++ project detected" >&2
    exit 0
fi

# Check for source files to analyze
if ! find . -maxdepth 10 -type f \( -name "*.c" -o -name "*.cpp" -o -name "*.cc" -o -name "*.cxx" \) \
    -not -path './.git/*' -not -path '*/build/*' 2>/dev/null | head -1 | grep -q .; then
    echo "No C/C++ source files found for cppcheck" >&2
    exit 0
fi

# Run cppcheck with XML output for structured parsing
set +e
cppcheck --enable=warning,style,performance,portability \
    --xml --xml-version=2 \
    --quiet \
    . 2>/tmp/cppcheck-output.xml
exit_code=$?
set -e

if [[ ! -f /tmp/cppcheck-output.xml ]]; then
    echo "cppcheck did not produce output" >&2
    exit 0
fi

# Parse XML output with Python (available in base image)
warnings=$(python3 - <<'PY'
import xml.etree.ElementTree as ET
import json
import sys

try:
    tree = ET.parse("/tmp/cppcheck-output.xml")
    root = tree.getroot()
    errors_elem = root.find("errors")
    if errors_elem is None:
        print("[]")
        sys.exit(0)

    warnings = []
    for error in errors_elem.findall("error"):
        severity = error.get("severity", "")
        if severity == "information":
            continue
        location = error.find("location")
        warnings.append({
            "file": location.get("file", "") if location is not None else "",
            "line": int(location.get("line", "0")) if location is not None else 0,
            "severity": severity,
            "message": error.get("msg", ""),
            "id": error.get("id", "")
        })

    print(json.dumps(warnings))
except Exception as e:
    print("[]", file=sys.stdout)
    print(f"Error parsing cppcheck output: {e}", file=sys.stderr)
PY
)

warning_count=$(echo "$warnings" | jq 'length')
passed=true
if [[ "$exit_code" -ne 0 ]] || [[ "$warning_count" -gt 0 ]]; then
    passed=false
fi

# Collect normalized lint data
echo "$warnings" | jq '{
    warnings: .,
    tool: "cppcheck",
    source: { tool: "cppcheck", integration: "code" }
}' | lunar collect -j ".lang.cpp.lint" -

# Collect raw cppcheck metadata
jq -n \
    --argjson passed "$passed" \
    --argjson exit_code "$exit_code" \
    --argjson warning_count "$warning_count" \
    '{
        passed: $passed,
        exit_code: $exit_code,
        warning_count: $warning_count,
        source: { tool: "cppcheck", integration: "code" }
    }' | lunar collect -j ".lang.cpp.native.cppcheck" -
