#!/bin/bash
set -e

# CI collector - extracts coverage from cargo-tarpaulin or cargo-llvm-cov

# Convert LUNAR_CI_COMMAND from JSON array to string if needed
CMD_RAW="$LUNAR_CI_COMMAND"
if [[ "$CMD_RAW" == "["* ]]; then
    CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
    CMD_STR="$CMD_RAW"
fi

coverage_pct=""
tool=""

# Check for tarpaulin output
if [[ "$CMD_STR" == *"tarpaulin"* ]]; then
    tool="cargo-tarpaulin"
    # tarpaulin writes coverage summary to stdout: "XX.XX% coverage, ..."
    # Also check for tarpaulin JSON report
    if [[ -f "tarpaulin-report.json" ]]; then
        coverage_pct=$(jq -r '.coverage // empty' tarpaulin-report.json 2>/dev/null || true)
    fi
    # Fallback: parse from CI output if available via LUNAR_CI_OUTPUT
    if [[ -z "$coverage_pct" ]] && [[ -n "$LUNAR_CI_OUTPUT" ]]; then
        coverage_pct=$(echo "$LUNAR_CI_OUTPUT" | grep -oP '[\d.]+(?=% coverage)' | tail -1 || true)
    fi
fi

# Check for llvm-cov output
if [[ "$CMD_STR" == *"llvm-cov"* ]]; then
    tool="cargo-llvm-cov"
    # llvm-cov can output JSON summary
    if [[ -f "coverage-summary.json" ]]; then
        coverage_pct=$(jq -r '.data[0].totals.lines.percent // empty' coverage-summary.json 2>/dev/null || true)
    fi
    # Check for lcov.info
    if [[ -z "$coverage_pct" ]] && [[ -f "lcov.info" ]]; then
        # Parse lcov format: sum of LH (lines hit) / LF (lines found)
        lh=$(grep -c '^LH:' lcov.info 2>/dev/null || echo "0")
        lf=$(grep -c '^LF:' lcov.info 2>/dev/null || echo "0")
        if [[ "$lf" -gt 0 ]]; then
            lh_sum=$(grep '^LH:' lcov.info | awk -F: '{s+=$2} END {print s}')
            lf_sum=$(grep '^LF:' lcov.info | awk -F: '{s+=$2} END {print s}')
            if [[ "$lf_sum" -gt 0 ]]; then
                coverage_pct=$(awk "BEGIN {printf \"%.1f\", ($lh_sum / $lf_sum) * 100}")
            fi
        fi
    fi
fi

if [[ -n "$coverage_pct" ]] && [[ -n "$tool" ]]; then
    lunar collect -j ".lang.rust.tests.coverage.percentage" "$coverage_pct"
    lunar collect ".lang.rust.tests.coverage.source.tool" "$tool" \
                  ".lang.rust.tests.coverage.source.integration" "ci"
fi
