#!/bin/bash
set -e

# Extract JaCoCo coverage from XML reports after test runs
# Uses yq for reliable XML parsing (installed via install.sh)

# Find JaCoCo XML report
coverage_file=""
# Maven standard location
if [[ -f "target/site/jacoco/jacoco.xml" ]]; then
    coverage_file="target/site/jacoco/jacoco.xml"
# Gradle standard location
elif [[ -f "build/reports/jacoco/test/jacocoTestReport.xml" ]]; then
    coverage_file="build/reports/jacoco/test/jacocoTestReport.xml"
fi

if [[ -z "$coverage_file" ]]; then
    echo "No JaCoCo report found, skipping coverage collection"
    exit 0
fi

echo "Found JaCoCo report: $coverage_file" >&2

# Use yq to parse XML and extract the report-level LINE counter
# JaCoCo XML: <report><counter type="LINE" missed="N" covered="N"/></report>
line_counter=$(yq -p xml -o json '.report.counter[] | select(.["+@type"] == "LINE")' "$coverage_file" 2>/dev/null || echo "")

if [[ -z "$line_counter" ]]; then
    echo "No LINE coverage data found in $coverage_file" >&2
    exit 0
fi

missed=$(echo "$line_counter" | yq '.["+@missed"]')
covered=$(echo "$line_counter" | yq '.["+@covered"]')

if [[ -z "$missed" || -z "$covered" || "$missed" == "null" || "$covered" == "null" ]]; then
    echo "Could not extract missed/covered from LINE counter" >&2
    exit 0
fi

total=$((missed + covered))

if [[ $total -gt 0 ]]; then
    coverage_pct=$(awk "BEGIN {printf \"%.2f\", ($covered * 100.0) / $total}")

    # Collect to .lang.java.tests.coverage (language-specific)
    lunar collect -j ".lang.java.tests.coverage.percentage" "$coverage_pct"
    lunar collect -j ".lang.java.tests.coverage.source" \
        '{"tool": "jacoco", "integration": "ci"}'

    # Collect to .testing.coverage (normalized, dual-write)
    lunar collect -j ".testing.coverage.percentage" "$coverage_pct"
    lunar collect -j ".testing.coverage.source" \
        '{"tool": "jacoco", "integration": "ci"}'
else
    echo "No LINE coverage data found in $coverage_file" >&2
fi
