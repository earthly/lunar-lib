#!/bin/bash
set -e

# Minimal placeholder: mark tests run with coverage ratio if available
# If a coverage report exists (coverage.xml), try to extract line-rate
coverage_pct=""
if [[ -f "coverage.xml" ]]; then
  coverage_pct=$(python - <<'PY' 2>/dev/null || true
import xml.etree.ElementTree as ET
try:
    tree = ET.parse("coverage.xml")
    root = tree.getroot()
    rate = root.get("line-rate")
    if rate is not None:
        pct = float(rate) * 100
        print(f"{pct:.2f}")
except Exception:
    pass
PY
)
fi

if [[ -n "$coverage_pct" ]]; then
  lunar collect -j .lang.python.tests.coverage.run true .lang.python.tests.coverage.percentage "$coverage_pct"
  jq -n \
    --argjson percentage "$(echo "$coverage_pct" | jq -r 'tonumber')" \
    '{
      source: { tool: "coverage", integration: "ci" },
      percentage: $percentage
    }' | lunar collect -j ".testing.coverage" -
else
  lunar collect -j .lang.python.tests.coverage.run true .lang.python.tests.coverage.percentage null
  jq -n 'null' | lunar collect -j ".testing.coverage" -
fi

