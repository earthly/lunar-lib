#!/bin/bash

set -e

# Attempt to find a Jacoco XML coverage report and extract line coverage.
# Common locations:
# - Maven:  target/site/jacoco/jacoco.xml
# - Gradle: build/reports/jacoco/test/jacocoTestReport.xml

coverage_file=""

if [[ -f "target/site/jacoco/jacoco.xml" ]]; then
  coverage_file="target/site/jacoco/jacoco.xml"
elif [[ -f "build/reports/jacoco/test/jacocoTestReport.xml" ]]; then
  coverage_file="build/reports/jacoco/test/jacocoTestReport.xml"
fi

coverage_pct=""

if [[ -n "$coverage_file" ]]; then
  echo "Found Java coverage file at: $coverage_file" >&2
  coverage_pct=$(python3 - <<PY 2>/dev/null || python - <<PY 2>/dev/null || true
import xml.etree.ElementTree as ET
from decimal import Decimal, ROUND_HALF_UP

path = "$coverage_file"
try:
    tree = ET.parse(path)
    root = tree.getroot()
    covered = 0
    missed = 0
    for c in root.iter("counter"):
        if c.get("type") == "LINE":
            missed += int(c.get("missed", "0"))
            covered += int(c.get("covered", "0"))
    total = covered + missed
    if total > 0:
        pct = (Decimal(covered) * Decimal(100) / Decimal(total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        print(pct)
except Exception:
    pass
PY
)
fi

if [[ -n "$coverage_pct" ]]; then
  # Collect to .lang.java.tests.coverage (language-specific)
  jq -n \
    --argjson run true \
    --argjson percentage "$(echo "$coverage_pct" | jq -r 'tonumber')" \
    '{
      run: $run,
      percentage: $percentage
    }' | lunar collect -j ".lang.java.tests.coverage" -

  # Also collect to .testing.coverage (standardized format)
  jq -n \
    --argjson percentage "$(echo "$coverage_pct" | jq -r 'tonumber')" \
    '{
      source: {
        tool: "jacoco",
        integration: "ci"
      },
      percentage: $percentage
    }' | lunar collect -j ".testing.coverage" -
else
  # Coverage file not found or could not extract percentage
  jq -n '{
    run: true,
    percentage: null
  }' | lunar collect -j ".lang.java.tests.coverage" -

  jq -n 'null' | lunar collect -j ".testing.coverage" -
fi


