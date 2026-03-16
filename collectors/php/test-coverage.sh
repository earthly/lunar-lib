#!/bin/bash
set -e

# CI collector - runs native on CI runner, avoid jq and heavy dependencies
# Extracts test coverage from PHPUnit's Clover XML output

# Convert LUNAR_CI_COMMAND from JSON array to string if needed
CMD_RAW="$LUNAR_CI_COMMAND"
if [[ "$CMD_RAW" == "["* ]]; then
    CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
    CMD_STR="$CMD_RAW"
fi

# Extract --coverage-clover path from command args using native bash
clover_path=""
prev=""
for arg in $CMD_STR; do
  if [[ "$prev" == "--coverage-clover" ]]; then
    clover_path="$arg"
    break
  fi
  # Also handle --coverage-clover=path format
  if [[ "$arg" == --coverage-clover=* ]]; then
    clover_path="${arg#--coverage-clover=}"
    break
  fi
  prev="$arg"
done

if [[ -z "$clover_path" || ! -f "$clover_path" ]]; then
  exit 0
fi

# Extract metrics from Clover XML
# Clover XML has <metrics> elements with statements/coveredstatements
total_stmts=$(sed -n 's/.*<metrics[^>]*statements="\([0-9]*\)".*/\1/p' "$clover_path" | head -1)
covered_stmts=$(sed -n 's/.*<metrics[^>]*coveredstatements="\([0-9]*\)".*/\1/p' "$clover_path" | head -1)

if [[ -z "$total_stmts" || -z "$covered_stmts" || "$total_stmts" == "0" ]]; then
  exit 0
fi

# Calculate percentage
coverage_pct=$(awk -v covered="$covered_stmts" -v total="$total_stmts" 'BEGIN {printf "%.2f", (covered / total) * 100}')

# Write to language-specific path
lunar collect -j ".lang.php.tests.coverage.percentage" "$coverage_pct"
lunar collect ".lang.php.tests.coverage.source.tool" "phpunit" \
             ".lang.php.tests.coverage.source.integration" "ci"

# Write to normalized .testing path (dual-write pattern)
lunar collect -j ".lang.php.tests.coverage.percentage" "$coverage_pct"
lunar collect -j ".testing.coverage.percentage" "$coverage_pct"
lunar collect -j ".testing.coverage.source" '{"tool":"phpunit","integration":"ci"}'

# Signal that tests were executed
lunar collect -j ".testing.source" '{"tool":"phpunit","integration":"ci"}'
