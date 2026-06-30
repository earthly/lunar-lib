#!/bin/bash
set -eo pipefail

# container-rescan: scan the most recently shipped container image for this
# component and write normalized results to .container_scan.
#
# Cron hook, runs in the Trivy collector image, clone-code: false. The image
# reference comes from already-persisted Component JSON — `.containers.builds[]`,
# written by the `docker` collector — read via `lunar component get-json`. That's
# a prior-eval read, not a same-eval collector dependency, so no dependency
# feature is required. Override the derived image with the `container_image`
# input.

echo "Running Trivy container image scan" >&2

# --- 1. Resolve the image reference to scan ---
IMAGE_REF="${LUNAR_INPUT_CONTAINER_IMAGE:-}"

if [ -z "$IMAGE_REF" ]; then
  COMPONENT_JSON=$(lunar component get-json "$LUNAR_COMPONENT_ID" 2>/dev/null || echo "")
  if [ -n "$COMPONENT_JSON" ]; then
    IMAGE_REF=$(echo "$COMPONENT_JSON" | jq -r '
      (.containers.builds // [])
      | map(select(.image != null and .image != ""))
      | last
      | if . == null then ""
        elif (.tag != null and .tag != "" and ((.image | contains(":")) | not))
          then "\(.image):\(.tag)"
        else .image end
    ' 2>/dev/null || echo "")
  fi
fi

if [ -z "$IMAGE_REF" ] || [ "$IMAGE_REF" = "null" ]; then
  echo "No container image to scan (no container_image input and no .containers.builds[] in component JSON) — skipping." >&2
  exit 0
fi

echo "Scanning image: $IMAGE_REF" >&2

# --- 2. Registry auth for private images (optional) ---
# Trivy reads registry credentials from TRIVY_USERNAME / TRIVY_PASSWORD.
if [ -n "${LUNAR_SECRET_REGISTRY_USERNAME:-}" ] && [ -n "${LUNAR_SECRET_REGISTRY_PASSWORD:-}" ]; then
  export TRIVY_USERNAME="$LUNAR_SECRET_REGISTRY_USERNAME"
  export TRIVY_PASSWORD="$LUNAR_SECRET_REGISTRY_PASSWORD"
fi

TRIVY_VERSION=$(trivy version -f json 2>/dev/null | jq -r '.Version // empty' || echo "")

RESULTS_FILE="/tmp/trivy-container-results.json"
if ! trivy image --scanners vuln --format json "$IMAGE_REF" > "$RESULTS_FILE" 2>/tmp/trivy-container-stderr.log; then
  echo "Trivy image scan failed for $IMAGE_REF — skipping vulnerability collection." >&2
  cat /tmp/trivy-container-stderr.log >&2 || true
  exit 0
fi

OS_FAMILY=$(jq -r '.Metadata.OS.Family // empty' "$RESULTS_FILE")
OS_VERSION=$(jq -r '.Metadata.OS.Name // empty' "$RESULTS_FILE")

# Preserve the raw Trivy results so policies can read fields we don't normalize.
lunar collect -j ".container_scan.native.trivy.results" - < "$RESULTS_FILE"

SOURCE_JSON=$(jq -n --arg version "$TRIVY_VERSION" '{
  tool: "trivy",
  integration: "cron"
} + (if $version != "" then {version: $version} else {} end)')

OS_JSON=$(jq -n --arg f "$OS_FAMILY" --arg v "$OS_VERSION" '
  if $f != "" then {os: ({family: $f} + (if $v != "" then {version: $v} else {} end))} else {} end')

VULN_COUNT=$(jq '[.Results[]? | .Vulnerabilities[]?] | length' "$RESULTS_FILE")
if [ "$VULN_COUNT" = "0" ] || [ -z "$VULN_COUNT" ]; then
  echo "No vulnerabilities found in $IMAGE_REF" >&2
  jq -n --argjson source "$SOURCE_JSON" --argjson os "$OS_JSON" --arg image "$IMAGE_REF" '{
    source: $source,
    image: $image,
    vulnerabilities: {critical: 0, high: 0, medium: 0, low: 0, total: 0},
    summary: {has_critical: false, has_high: false, all_fixable: true}
  } + $os' | lunar collect -j ".container_scan" -
  exit 0
fi

# Normalize into the tool-agnostic .container_scan schema (mirrors auto.sh's
# .sca normalization; adds image + os).
jq -c --argjson source "$SOURCE_JSON" --argjson os "$OS_JSON" --arg image "$IMAGE_REF" '{
  source: $source,
  image: $image,
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
    has_high:     ([.Results[]?.Vulnerabilities[]? | select(.Severity == "HIGH")]     | length > 0),
    all_fixable:  ([.Results[]?.Vulnerabilities[]? | select(.FixedVersion == null or .FixedVersion == "")] | length == 0)
  }
} + $os' "$RESULTS_FILE" | lunar collect -j ".container_scan" -

echo "Found $VULN_COUNT vulnerabilities in $IMAGE_REF" >&2
