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
# --redact blanks the detected credential in the report: .Secret becomes
# "REDACTED" and the same substring is masked inside .Match. Without it the
# report ships the live secret to Component JSON.
REPORT_FILE="/tmp/gitleaks-report.json"
EXIT_CODE=0
gitleaks detect --no-git --source . --redact --report-path "$REPORT_FILE" --report-format json 2>&1 >&2 || EXIT_CODE=$?

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

  # Collect raw report to native path. Only ship it once --redact is confirmed
  # to have taken effect — the flag's help text only promises redaction of
  # "logs and stdout", so treat a report that still carries a live .Secret as a
  # failure and drop the raw report rather than leaking it. The normalized
  # .secrets.issues below is unaffected, so policies keep working either way.
  if jq -e 'all(.[]; .Secret == "REDACTED")' "$REPORT_FILE" >/dev/null 2>&1; then
    lunar collect -j ".secrets.native.gitleaks.auto.report" - < "$REPORT_FILE"
  else
    echo "Report is not redacted as expected; dropping raw report to avoid storing plaintext secrets" >&2
  fi

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
