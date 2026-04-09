#!/bin/bash
set -e

echo "Running Checkov scan collector" >&2

# Quick detection: do any IaC files exist?
# Check for common IaC file patterns before running Checkov
IAC_FOUND=false

for pattern in "*.tf" "*.bicep" "serverless.yml" "serverless.yaml"; do
  if find . -name "$pattern" ! -path "*/.git/*" ! -path "*/node_modules/*" ! -path "*/.terraform/*" -print -quit 2>/dev/null | grep -q .; then
    IAC_FOUND=true
    break
  fi
done

# Check Dockerfiles (pattern matching for Dockerfile, Dockerfile.*, *.dockerfile)
if ! $IAC_FOUND; then
  if find . \( -name "Dockerfile" -o -name "Dockerfile.*" -o -name "*.dockerfile" \) \
     ! -path "*/.git/*" ! -path "*/node_modules/*" -print -quit 2>/dev/null | grep -q .; then
    IAC_FOUND=true
  fi
fi

# Check YAML files for K8s or CloudFormation markers
if ! $IAC_FOUND; then
  YAML_FILES=$(find . \( -name "*.yaml" -o -name "*.yml" \) \
    ! -path "*/.git/*" ! -path "*/node_modules/*" ! -path "*/.github/*" \
    2>/dev/null | head -100)
  for f in $YAML_FILES; do
    if head -30 "$f" 2>/dev/null | grep -qE '(apiVersion:|AWSTemplateFormatVersion)'; then
      IAC_FOUND=true
      break
    fi
  done
fi

if ! $IAC_FOUND; then
  echo "No IaC files detected, skipping" >&2
  exit 0
fi

# Collect IaC file paths to signal IaC presence for policy skip logic
IAC_FILES=$(find . \( -name "*.tf" -o -name "Dockerfile" -o -name "Dockerfile.*" \
  -o -name "*.dockerfile" -o -name "*.bicep" -o -name "serverless.yml" -o -name "serverless.yaml" \) \
  ! -path "*/.git/*" ! -path "*/node_modules/*" ! -path "*/.terraform/*" \
  2>/dev/null | head -50 | sed 's|^\./||')

echo "$IAC_FILES" | jq -R 'select(length > 0) | {path: .}' | jq -s '.' | lunar collect -j ".iac.files" -

# Record source metadata
CHECKOV_VERSION=$(checkov --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "")
lunar collect ".iac_scan.source.tool" "checkov"
lunar collect ".iac_scan.source.integration" "code"
if [ -n "$CHECKOV_VERSION" ]; then
  lunar collect ".iac_scan.source.version" "$CHECKOV_VERSION"
fi

# Run Checkov with JSON output
REPORT_FILE="/tmp/checkov-report.json"
EXIT_CODE=0
checkov -d . --output json --quiet --compact > "$REPORT_FILE" 2>/dev/null || EXIT_CODE=$?

# Exit codes: 0 = all pass, 1 = failures found, anything else = error
if [ "$EXIT_CODE" -gt 1 ]; then
  echo "Checkov error (exit code $EXIT_CODE), skipping result collection" >&2
  # Still write zero findings so policy has data to evaluate
  lunar collect -j ".iac_scan.findings" '{"critical":0,"high":0,"medium":0,"low":0,"total":0}'
  lunar collect -j ".iac_scan.summary" '{"has_critical":false,"has_high":false,"has_medium":false,"has_low":false}'
  exit 0
fi

# Validate we got valid JSON
if [ ! -s "$REPORT_FILE" ] || ! jq empty "$REPORT_FILE" 2>/dev/null; then
  echo "No valid Checkov JSON output" >&2
  lunar collect -j ".iac_scan.findings" '{"critical":0,"high":0,"medium":0,"low":0,"total":0}'
  lunar collect -j ".iac_scan.summary" '{"has_critical":false,"has_high":false,"has_medium":false,"has_low":false}'
  exit 0
fi

# Normalize: Checkov output can be a single object or array of objects (multiple frameworks)
# Merge all framework results into unified counts
jq '
  (if type == "array" then . else [.] end) as $frameworks |

  # Collect all failed checks across frameworks
  [$frameworks[] | .results.failed_checks[]?] as $failed |

  # Count by severity (Checkov uses uppercase: CRITICAL, HIGH, MEDIUM, LOW)
  ($failed | map(select(.severity == "CRITICAL")) | length) as $critical |
  ($failed | map(select(.severity == "HIGH")) | length) as $high |
  ($failed | map(select(.severity == "MEDIUM")) | length) as $medium |
  # LOW includes LOW, INFO, and null/unassigned severity
  ($failed | map(select(.severity == "LOW" or .severity == "INFO" or .severity == null or .severity == "UNKNOWN")) | length) as $low |
  ($failed | length) as $total |

  # Summary counts from Checkov
  ($frameworks | map(.summary.passed // 0) | add) as $passed |
  ($frameworks | map(.summary.failed // 0) | add) as $failed_count |
  ($frameworks | map(.summary.skipped // 0) | add) as $skipped |

  # Cap native findings at 100
  [$failed[:100][] | {
    check_id: (.check_id // .check.id // "unknown"),
    check_name: (.check.name // .check_id // "unknown"),
    severity: ((.severity // "UNKNOWN") | ascii_downcase),
    resource: (.resource // "unknown"),
    file: (.file_path // "unknown"),
    file_line_range: (.file_line_range // [])
  }] as $native_findings |

  {
    findings: {
      critical: $critical,
      high: $high,
      medium: $medium,
      low: $low,
      total: $total
    },
    summary: {
      has_critical: ($critical > 0),
      has_high: ($high > 0),
      has_medium: ($medium > 0),
      has_low: ($low > 0)
    },
    native: {
      passed: $passed,
      failed: $failed_count,
      skipped: $skipped,
      findings: $native_findings
    }
  }
' "$REPORT_FILE" > /tmp/checkov-parsed.json

# Write normalized findings
jq '.findings' /tmp/checkov-parsed.json | lunar collect -j ".iac_scan.findings" -
jq '.summary' /tmp/checkov-parsed.json | lunar collect -j ".iac_scan.summary" -
jq '.native' /tmp/checkov-parsed.json | lunar collect -j ".iac_scan.native.checkov.auto" -

# Summary for logs
TOTAL=$(jq '.findings.total' /tmp/checkov-parsed.json)
CRITICAL=$(jq '.findings.critical' /tmp/checkov-parsed.json)
HIGH=$(jq '.findings.high' /tmp/checkov-parsed.json)
MEDIUM=$(jq '.findings.medium' /tmp/checkov-parsed.json)
LOW=$(jq '.findings.low' /tmp/checkov-parsed.json)
echo "Checkov scan complete: $TOTAL finding(s) ($CRITICAL critical, $HIGH high, $MEDIUM medium, $LOW low)" >&2
