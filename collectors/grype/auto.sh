#!/bin/bash
set -eo pipefail

echo "Running Grype vulnerability scan" >&2

# Grype scans the repository filesystem (dependency manifests + lockfiles) for
# known CVEs. `dir:.` catalogs packages across all supported ecosystems in one
# pass.
#
# Use the vulnerability DB pre-baked into the image (see Earthfile); do NOT
# download/decompress it at scan time. Grype's DB decompresses to ~1.7GB, and
# materializing it at runtime OOM-kills the memory-limited collector container
# (exit 137) — confirmed on the hub with BOTH the default cache and a
# disk-backed cache, so it's the runtime DB materialization itself, not the
# cache location. The baked DB sits in a read-only image layer and is queried
# on-disk via SQLite (low memory). Freshness is tied to image rebuild cadence;
# VALIDATE_AGE is disabled so a slightly-older image's DB isn't rejected.
export GRYPE_DB_CACHE_DIR="${GRYPE_DB_CACHE_DIR:-/opt/grype/db}"
export GRYPE_DB_AUTO_UPDATE=false
export GRYPE_DB_VALIDATE_AGE=false
# Keep Go's heap tight during package cataloging + matching.
export GOGC=40

RESULTS_FILE="/tmp/grype-results.json"

if ! grype "dir:." -o json > "$RESULTS_FILE" 2>/tmp/grype-stderr.log; then
  echo "Grype scan failed — skipping vulnerability collection" >&2
  cat /tmp/grype-stderr.log >&2 || true
  exit 0
fi

# Grype version comes straight from the scan descriptor — no separate version call.
GRYPE_VERSION=$(jq -r '.descriptor.version // empty' "$RESULTS_FILE")

# Preserve the raw Grype matches so policies can read fields we don't normalize
# (CVSS scores, dataSource, relatedVulnerabilities, full fix state, etc.).
jq -c '.matches // []' "$RESULTS_FILE" | lunar collect -j ".sca.native.grype.matches" -

# Build source metadata JSON
SOURCE_JSON=$(jq -n --arg version "$GRYPE_VERSION" '{
  tool: "grype",
  integration: "code"
} + (if $version != "" then {version: $version} else {} end)')

# Check if any vulnerabilities found
VULN_COUNT=$(jq '.matches | length' "$RESULTS_FILE")
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

# Normalize into the tool-agnostic .sca schema.
# Grype severities are Critical/High/Medium/Low/Negligible/Unknown. The .sca
# schema has only critical/high/medium/low buckets, so:
#   - Negligible folds into `low` (both in counts and in finding severity)
#   - Unknown has no bucket but still counts toward `total`
# fixable = (fix.state == "fixed"); fix_version = first fixed version.
jq -c --argjson source "$SOURCE_JSON" '
  def sev: (.vulnerability.severity // "Unknown") | ascii_downcase;
  {
    source: $source,
    vulnerabilities: {
      critical: [.matches[] | select(sev == "critical")] | length,
      high:     [.matches[] | select(sev == "high")]     | length,
      medium:   [.matches[] | select(sev == "medium")]   | length,
      low:      [.matches[] | select(sev == "low" or sev == "negligible")] | length,
      total:    (.matches | length)
    },
    findings: [.matches[] | {
      severity:    (if sev == "negligible" then "low" else sev end),
      package:     .artifact.name,
      version:     .artifact.version,
      ecosystem:   .artifact.type,
      cve:         .vulnerability.id,
      title:       (.vulnerability.description // null),
      fix_version: ((.vulnerability.fix.versions // [])[0] // null),
      fixable:     (.vulnerability.fix.state == "fixed")
    }],
    summary: {
      has_critical: ([.matches[] | select(sev == "critical")] | length > 0),
      has_high:     ([.matches[] | select(sev == "high")]     | length > 0),
      all_fixable:  ([.matches[] | select(.vulnerability.fix.state != "fixed")] | length == 0)
    }
  }' "$RESULTS_FILE" | lunar collect -j ".sca" -

echo "Found $VULN_COUNT vulnerabilities" >&2
