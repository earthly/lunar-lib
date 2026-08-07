#!/bin/bash
set -eo pipefail

# Scan the most recently shipped container image for this component and write
# normalized results to .container_scan.
#
# Shared by two sub-collectors: the on-push `container-scan` (after-json hook)
# and the scheduled `container-rescan` (cron). Both run in the Trivy collector
# image, no code clone. The image is resolved from the docker collector's
# pushed-image record (.containers.native.docker.cicd.cmds[]) via
# `lunar component get-json`, or pinned with the `container_image` input. Only
# source.integration differs between the two.

echo "Running Trivy container image scan" >&2

# On-push (after-json) vs scheduled (cron) — same scan, label the source so
# consumers can tell which fired. container-scan → after-json; anything else
# (container-rescan) keeps the original cron label.
case "${LUNAR_COLLECTOR_NAME:-}" in
  *container-scan) INTEGRATION="after-json" ;;
  *)               INTEGRATION="cron" ;;
esac

# --- 1. Resolve the image reference to scan ---
IMAGE_REF="${LUNAR_VAR_CONTAINER_IMAGE:-}"

if [ -z "$IMAGE_REF" ]; then
  # Derive the image from what the component actually PUSHED, not just what it
  # built. The docker collector records every CI docker command in
  # .containers.native.docker.cicd.cmds[]; we take the most recent one that
  # shipped an image — a `docker push <ref>`, or a build with `--push`
  # (`docker build --push` / `docker buildx build --push -t <ref>`).
  # .containers.builds[] is "what was built" (test/dry-run builds that never
  # shipped land there too, and a push in a separate job isn't reflected), so
  # it's the wrong source for "what shipped". (Per Fry review on #221.)
  COMPONENT_JSON=$(lunar component get-json "$LUNAR_COMPONENT_ID" 2>/dev/null || echo "")
  if [ -n "$COMPONENT_JSON" ]; then
    IMAGE_REF=$(echo "$COMPONENT_JSON" | jq -r '
      def ref_if_pushed:
        (split(" ") | map(select(. != ""))) as $t
        | (($t[1:] | map(select(startswith("-") | not)) | first) // "") as $sub
        | if $sub == "push"
          then ((($t | index("push")) // -1) as $pi
                | if $pi < 0 then "" else ($t[($pi+1):] | map(select(startswith("-") | not)) | first // "") end)
          elif ($t | any(. == "--push"))
          then ([ range(0; ($t | length)) as $i | select($t[$i] == "-t" or $t[$i] == "--tag") | $t[$i+1] ] | first // "")
          else "" end;
      (.containers.native.docker.cicd.cmds // [])
      | map((.cmd // "") | ref_if_pushed)
      | map(select(. != "" and . != null))
      | last // ""
    ' 2>/dev/null || echo "")
  fi
fi

if [ -z "$IMAGE_REF" ] || [ "$IMAGE_REF" = "null" ]; then
  echo "No pushed container image to scan (no container_image input and no 'docker push' / '--push' build in .containers.native.docker.cicd.cmds[]) — skipping." >&2
  exit 0
fi

echo "Scanning image: $IMAGE_REF" >&2

# --- 2. Registry auth for private images (optional) ---
# Trivy reads registry credentials from TRIVY_USERNAME / TRIVY_PASSWORD. The
# username is accepted under either REGISTRY_USERNAME or REGISTRY_USER — both are
# common registry/CI conventions, so match whatever the deployer already has.
REG_USER="${LUNAR_SECRET_REGISTRY_USERNAME:-${LUNAR_SECRET_REGISTRY_USER:-}}"
if [ -n "$REG_USER" ] && [ -n "${LUNAR_SECRET_REGISTRY_PASSWORD:-}" ]; then
  export TRIVY_USERNAME="$REG_USER"
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

# Source metadata (integration set above: after-json on-push, or cron re-scan).
SOURCE_JSON=$(jq -n --arg version "$TRIVY_VERSION" --arg integration "$INTEGRATION" '{
  tool: "trivy",
  integration: $integration
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
