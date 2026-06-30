#!/bin/bash
set -eo pipefail

# container-rescan: scan the most recently shipped container image for this
# component and write normalized results to .container_scan.
#
# Cron hook, runs in the Grype collector image (baked-in vulnerability DB),
# clone-code: false. The image reference comes from already-persisted Component
# JSON — `.containers.builds[]`, written by the `docker` collector — read via
# `lunar component get-json`. That's a prior-eval read, not a same-eval
# collector dependency, so no dependency feature is required. Override the
# derived image with the `container_image` input.

echo "Running Grype container image scan" >&2

# --- 1. Resolve the image reference to scan ---
IMAGE_REF="${LUNAR_INPUT_CONTAINER_IMAGE:-}"

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
# Grype/Stereoscope reads registry credentials from these env vars. Public
# images need none.
if [ -n "${LUNAR_SECRET_REGISTRY_USERNAME:-}" ] && [ -n "${LUNAR_SECRET_REGISTRY_PASSWORD:-}" ]; then
  export GRYPE_REGISTRY_AUTH_USERNAME="$LUNAR_SECRET_REGISTRY_USERNAME"
  export GRYPE_REGISTRY_AUTH_PASSWORD="$LUNAR_SECRET_REGISTRY_PASSWORD"
fi

# Scan against the DB baked into the image (same default as auto.sh).
export GRYPE_DB_CACHE_DIR="${GRYPE_DB_CACHE_DIR:-/opt/grype/db}"
export GRYPE_DB_AUTO_UPDATE=false
export GRYPE_DB_VALIDATE_AGE=false
export GOGC=40

RESULTS_FILE="/tmp/grype-container-results.json"
if ! grype "$IMAGE_REF" -o json > "$RESULTS_FILE" 2>/tmp/grype-container-stderr.log; then
  echo "Grype image scan failed for $IMAGE_REF — skipping vulnerability collection." >&2
  cat /tmp/grype-container-stderr.log >&2 || true
  exit 0
fi

GRYPE_VERSION=$(jq -r '.descriptor.version // empty' "$RESULTS_FILE")
OS_FAMILY=$(jq -r '.distro.name // empty' "$RESULTS_FILE")
OS_VERSION=$(jq -r '.distro.version // empty' "$RESULTS_FILE")

# Preserve the raw matches so policies can read fields we don't normalize.
jq -c '.matches // []' "$RESULTS_FILE" | lunar collect -j ".container_scan.native.grype.matches" -

# Source metadata (integration=cron; this is the scheduled re-scan).
SOURCE_JSON=$(jq -n --arg version "$GRYPE_VERSION" '{
  tool: "grype",
  integration: "cron"
} + (if $version != "" then {version: $version} else {} end)')

# os{} block, included only when Grype reported a distro.
OS_JSON=$(jq -n --arg f "$OS_FAMILY" --arg v "$OS_VERSION" '
  if $f != "" then {os: ({family: $f} + (if $v != "" then {version: $v} else {} end))} else {} end')

VULN_COUNT=$(jq '.matches | length' "$RESULTS_FILE")
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
# .sca normalization; adds image + os). Negligible folds into low; Unknown
# still counts toward total.
jq -c --argjson source "$SOURCE_JSON" --argjson os "$OS_JSON" --arg image "$IMAGE_REF" '
  def sev: (.vulnerability.severity // "Unknown") | ascii_downcase;
  {
    source: $source,
    image: $image,
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
  } + $os' "$RESULTS_FILE" | lunar collect -j ".container_scan" -

echo "Found $VULN_COUNT vulnerabilities in $IMAGE_REF" >&2
