#!/bin/bash
set -eo pipefail

echo "Running Trivy vulnerability scan" >&2

# Get Trivy version for source metadata
TRIVY_VERSION=$(trivy version -f json 2>/dev/null | jq -r '.Version // empty' || trivy version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' || echo "")

# Run Trivy filesystem scan (vuln scanner only, JSON output)
RESULTS_FILE="/tmp/trivy-results.json"
SCAN_OK=false

if trivy fs --scanners vuln --format json . > "$RESULTS_FILE" 2>/tmp/trivy-stderr.log; then
  SCAN_OK=true
else
  echo "Full repo scan failed — falling back to individual manifest scanning" >&2

  # Find dependency manifests and scan each individually, merging results.
  # This handles multi-module repos where one bad pom.xml would kill the whole scan.
  MANIFESTS=$(find . -maxdepth 4 -type f \( \
    -name "go.sum" -o -name "package-lock.json" -o -name "yarn.lock" -o -name "pnpm-lock.yaml" \
    -o -name "requirements.txt" -o -name "Pipfile.lock" -o -name "poetry.lock" \
    -o -name "Gemfile.lock" -o -name "Cargo.lock" \
    -o -name "pom.xml" -o -name "build.gradle" -o -name "build.gradle.kts" \
    -o -name "composer.lock" -o -name "packages.lock.json" \
  \) ! -path "*/vendor/*" ! -path "*/node_modules/*" 2>/dev/null)

  if [ -z "$MANIFESTS" ]; then
    echo "No dependency manifests found — nothing to scan" >&2
    exit 0
  fi

  # Scan each manifest, collect all results
  echo '{"Results":[]}' > "$RESULTS_FILE"
  SCANNED=0
  while IFS= read -r manifest; do
    echo "  Scanning $manifest..." >&2
    if trivy fs --scanners vuln --format json "$manifest" > /tmp/trivy-single.json 2>/dev/null; then
      # Merge Results arrays
      jq -s '.[0].Results += (.[1].Results // []) | .[0]' "$RESULTS_FILE" /tmp/trivy-single.json > /tmp/trivy-merged.json
      mv /tmp/trivy-merged.json "$RESULTS_FILE"
      SCANNED=$((SCANNED + 1))
    fi
  done <<< "$MANIFESTS"

  if [ "$SCANNED" -gt 0 ]; then
    SCAN_OK=true
    echo "Scanned $SCANNED manifests individually" >&2
  else
    echo "No manifests could be scanned — skipping vulnerability collection" >&2
    exit 0
  fi
fi

if [ "$SCAN_OK" != "true" ]; then
  exit 0
fi

# Build source metadata JSON
SOURCE_JSON=$(jq -n --arg version "$TRIVY_VERSION" '{
  tool: "trivy",
  integration: "code"
} + (if $version != "" then {version: $version} else {} end)')

# Check if any vulnerabilities found
VULN_COUNT=$(jq '[.Results[]? | .Vulnerabilities[]?] | length' "$RESULTS_FILE")
if [ "$VULN_COUNT" = "0" ] || [ -z "$VULN_COUNT" ]; then
  echo "No vulnerabilities found" >&2
  # Write everything in a single collect call to avoid merge fragmentation
  jq -n --argjson source "$SOURCE_JSON" '{
    source: $source,
    vulnerabilities: {critical: 0, high: 0, medium: 0, low: 0, total: 0},
    summary: {has_critical: false, has_high: false, all_fixable: true}
  }' | lunar collect -j ".sca" -
  exit 0
fi

# Build normalized findings, counts, and source in a single JSON blob
jq -c --argjson source "$SOURCE_JSON" '{
  source: $source,
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
