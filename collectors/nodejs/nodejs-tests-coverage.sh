#!/bin/bash
set -e

# Attempt to run jest coverage summary quickly; if jest not available, mark run with null percentage.
coverage_pct=""
if command -v npx >/dev/null 2>&1; then
  coverage_pct=$(npx --yes jest --coverage --coverageReporters=text 2>/dev/null | grep "All files" | awk '{print $4}' | sed 's/%//' || true)
fi

if [[ -n "$coverage_pct" ]]; then
  lunar collect -j .lang.nodejs.tests.coverage.run true .lang.nodejs.tests.coverage.percentage "$coverage_pct"
  jq -n \
    --argjson percentage "$(echo "$coverage_pct" | jq -r 'tonumber')" \
    '{
      source: { tool: "jest", integration: "ci" },
      percentage: $percentage
    }' | lunar collect -j ".testing.coverage" -
else
  lunar collect -j .lang.nodejs.tests.coverage.run true .lang.nodejs.tests.coverage.percentage null
  jq -n 'null' | lunar collect -j ".testing.coverage" -
fi

