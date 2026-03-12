#!/bin/bash
set -e

echo "Running gitleaks scan collector" >&2

# Verify gitleaks is available
if ! command -v gitleaks >/dev/null 2>&1; then
  echo "gitleaks not found; skipping" >&2
  exit 0
fi

# Record source metadata
GITLEAKS_VERSION=$(gitleaks version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' || echo "")
lunar collect ".secrets.source.tool" "gitleaks"
lunar collect ".secrets.source.integration" "code"
if [ -n "$GITLEAKS_VERSION" ]; then
  lunar collect ".secrets.source.version" "$GITLEAKS_VERSION"
fi

# Run gitleaks scan (exit code 1 = leaks found, which is expected)
REPORT_FILE="/tmp/gitleaks-report.json"
GITLEAKS_EXIT=0
gitleaks detect --source . --report-format json --report-path "$REPORT_FILE" --no-git 2>/dev/null || GITLEAKS_EXIT=$?

# Exit code 2+ means gitleaks itself errored
if [ "$GITLEAKS_EXIT" -ge 2 ]; then
  echo "gitleaks exited with error code $GITLEAKS_EXIT" >&2
  exit 0
fi

# Parse results
if [ ! -f "$REPORT_FILE" ] || [ ! -s "$REPORT_FILE" ]; then
  # No report file or empty — clean scan
  lunar collect -j ".secrets.findings.total" 0
  lunar collect -j ".secrets.clean" true
  lunar collect -j ".secrets.issues" '[]'
  exit 0
fi

# Count findings
TOTAL=$(jq 'length' "$REPORT_FILE")

if [ "$TOTAL" -eq 0 ]; then
  lunar collect -j ".secrets.findings.total" 0
  lunar collect -j ".secrets.clean" true
  lunar collect -j ".secrets.issues" '[]'
  exit 0
fi

# Findings detected — normalize issues
lunar collect -j ".secrets.findings.total" "$TOTAL"
lunar collect -j ".secrets.clean" false

# Build normalized issues array (limit to first 50 to avoid oversized payloads)
jq '[.[:50] | .[] | {
  rule: .RuleID,
  file: .File,
  line: .StartLine,
  secret_type: .Description,
  commit: .Commit
}]' "$REPORT_FILE" | lunar collect -j ".secrets.issues" -

# Store raw report under native (limited to first 50)
jq '{"report": .[:50]}' "$REPORT_FILE" | lunar collect -j ".secrets.native.gitleaks.auto" -
