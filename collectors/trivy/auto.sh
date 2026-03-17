#!/bin/bash
set -e

echo "Running Trivy vulnerability scan" >&2

# Record source metadata
TRIVY_VERSION=$(trivy version -f json 2>/dev/null | jq -r '.Version // empty' || trivy version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' || echo "")
lunar collect ".sca.source.tool" "trivy"
lunar collect ".sca.source.integration" "code"
if [ -n "$TRIVY_VERSION" ]; then
  lunar collect ".sca.source.version" "$TRIVY_VERSION"
fi

# Run Trivy filesystem scan (vuln scanner only, JSON output)
RESULTS_FILE="/tmp/trivy-results.json"
if ! trivy fs --scanners vuln --format json --quiet . > "$RESULTS_FILE" 2>/dev/null; then
  echo "Trivy scan failed" >&2
  exit 1
fi

# Check if any vulnerabilities found
VULN_COUNT=$(jq '[.Results[]? | .Vulnerabilities[]?] | length' "$RESULTS_FILE")
if [ "$VULN_COUNT" = "0" ] || [ -z "$VULN_COUNT" ]; then
  echo "No vulnerabilities found" >&2
  # Write zero counts so policies can verify scan ran
  jq -n '{
    vulnerabilities: {critical: 0, high: 0, medium: 0, low: 0, total: 0},
    summary: {has_critical: false, has_high: false, all_fixable: true}
  }' | lunar collect -j ".sca" -
  exit 0
fi

# Build normalized findings and counts
jq -c '{
  vulnerabilities: {
    critical: [.Results[]?.Vulnerabilities[]? | select(.Severity == "CRITICAL")] | length,
    high:     [.Results[]?.Vulnerabilities[]? | select(.Severity == "HIGH")]     | length,
    medium:   [.Results[]?.Vulnerabilities[]? | select(.Severity == "MEDIUM")]   | length,
    low:      [.Results[]?.Vulnerabilities[]? | select(.Severity == "LOW")]      | length,
    total:    [.Results[]?.Vulnerabilities[]?] | length
  },
  findings: [.Results[] as $r | $r.Vulnerabilities[]? | {
    severity:    (.Severity | ascii_downcase),
    package:     .PkgName,
    version:     .InstalledVersion,
    ecosystem:   $r.Type,
    cve:         .VulnerabilityID,
    title:       .Title,
    fix_version: (.FixedVersion // null),
    fixable:     (.FixedVersion != null and .FixedVersion != "")
  }],
  summary: {
    has_critical: ([.Results[]?.Vulnerabilities[]? | select(.Severity == "CRITICAL")] | length > 0),
    has_high:     ([.Results[]?.Vulnerabilities[]? | select(.Severity == "HIGH")] | length > 0),
    all_fixable:  ([.Results[]?.Vulnerabilities[]? | select(.FixedVersion == null or .FixedVersion == "")] | length == 0)
  }
}' "$RESULTS_FILE" | lunar collect -j ".sca" -

echo "Found $VULN_COUNT vulnerabilities" >&2
