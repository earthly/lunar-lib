#!/bin/bash
set -e

# Extract coverage from coverage.xml after pytest runs
# Runs as native (no jq) — use grep/awk for XML parsing

# Look for coverage.xml (pytest-cov default output)
COVERAGE_FILE="coverage.xml"
if [[ ! -f "$COVERAGE_FILE" ]]; then
    # Try common alternative locations
    for f in htmlcov/coverage.xml .coverage.xml; do
        if [[ -f "$f" ]]; then
            COVERAGE_FILE="$f"
            break
        fi
    done
fi

if [[ ! -f "$COVERAGE_FILE" ]]; then
    echo "No coverage.xml found, skipping"
    exit 0
fi

# Extract line-rate from the coverage XML (Cobertura format)
line_rate=$(sed -n 's/.*line-rate="\([^"]*\)".*/\1/p' "$COVERAGE_FILE" | head -1)

if [[ -z "$line_rate" ]]; then
    echo "Could not extract line-rate from $COVERAGE_FILE"
    exit 0
fi

# Convert to percentage (line-rate is 0.0-1.0)
# Use awk for floating point math (available in all environments)
coverage_pct=$(awk -v rate="$line_rate" 'BEGIN {printf "%.2f", rate * 100}')

# Write to language-specific path
lunar collect -j ".lang.python.tests.coverage.percentage" "$coverage_pct"
lunar collect -j ".lang.python.tests.coverage.source" '{"tool":"coverage","integration":"ci"}'

# Write to normalized .testing path (dual-write pattern)
lunar collect -j ".testing.coverage.percentage" "$coverage_pct"
lunar collect -j ".testing.coverage.source" '{"tool":"coverage","integration":"ci"}'

# Signal that tests were executed
lunar collect -j ".testing.source" '{"tool":"pytest","integration":"ci"}'
