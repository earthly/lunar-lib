#!/bin/bash
set -e

echo "Running gitleaks scan collector" >&2

# Record source metadata
GITLEAKS_VERSION=$(gitleaks version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1 || echo "")
lunar collect ".secrets.source.tool" "gitleaks"
lunar collect ".secrets.source.integration" "code"
if [ -n "$GITLEAKS_VERSION" ]; then
  lunar collect ".secrets.source.version" "$GITLEAKS_VERSION"
fi

# Run gitleaks in --no-git mode (no git history needed, scan working directory)
REPORT_FILE="/tmp/gitleaks-report.json"
EXIT_CODE=0
gitleaks detect --no-git --source . --report-path "$REPORT_FILE" --report-format json 2>&1 >&2 || EXIT_CODE=$?

# Exit code 1 = leaks found, 0 = clean, anything else = error
if [ "$EXIT_CODE" -gt 1 ]; then
  echo "gitleaks exited with unexpected code $EXIT_CODE" >&2
  exit 1
fi

# Parse findings from report
if [ -f "$REPORT_FILE" ] && [ -s "$REPORT_FILE" ]; then
  FINDING_COUNT=$(jq 'length' "$REPORT_FILE")
  echo "Gitleaks found $FINDING_COUNT finding(s)" >&2

  # Cap at 50 findings to avoid oversized Component JSON
  if [ "$FINDING_COUNT" -gt 50 ]; then
    echo "Capping at 50 findings (out of $FINDING_COUNT)" >&2
    jq '.[0:50]' "$REPORT_FILE" > /tmp/gitleaks-capped.json
    mv /tmp/gitleaks-capped.json "$REPORT_FILE"
  fi

  # Collect raw report to native path
  cat "$REPORT_FILE" | lunar collect -j ".secrets.native.gitleaks.auto.report" -

  # Normalize findings into .secrets.issues
  jq '[.[] | {
    rule: .RuleID,
    file: .File,
    line: .StartLine,
    secret_type: .Description
  }]' "$REPORT_FILE" | lunar collect -j ".secrets.issues" -
else
  echo "No findings detected" >&2
  lunar collect -j ".secrets.issues" "[]"
fi
