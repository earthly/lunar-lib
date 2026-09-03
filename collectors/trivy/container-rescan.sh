#!/bin/bash
set -eo pipefail

# Scan every container image this component shipped and write normalized,
# per-image results to .container_scan.
#
# Shared by two sub-collectors: the on-push `container-scan` (after-json hook)
# and the scheduled `container-rescan` (cron). Both run in the Trivy collector
# image, no code clone. The images are resolved from the docker collector's
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

# --- 1. Resolve the image references to scan ---
# `container_image` pins one ref, or a comma/whitespace-separated list.
IMAGE_REFS=()
if [ -n "${LUNAR_VAR_CONTAINER_IMAGE:-}" ]; then
  # shellcheck disable=SC2206
  IMAGE_REFS=(${LUNAR_VAR_CONTAINER_IMAGE//,/ })
else
  # Derive the images from what the component actually PUSHED, not just what it
  # built. The docker collector records every CI docker command in
  # .containers.native.docker.cicd.cmds[]; we take every one that shipped an
  # image — a `docker push <ref>`, or a build with `--push` (`docker build
  # --push` / `docker buildx build --push -t <ref>`) — in push order, the same
  # ref pushed twice counting once. .containers.builds[] is "what was built"
  # (test/dry-run builds that never shipped land there too, and a push in a
  # separate job isn't reflected), so it's the wrong source for "what shipped".
  # (Per Fry review on #221.)
  #
  # In PR context, pin the lookup to the commit being scanned. get-json does not
  # default these from the environment: with neither flag it resolves the
  # default-branch snapshot (`WHERE pr IS NULL`), so on a PR it returns main's
  # Component JSON — a different commit, whose docker record does not carry this
  # PR's pushed images — and the scan below skips. --git-sha alongside --pr
  # narrows to the exact commit instead of the PR's latest, so the results
  # describe the images this commit actually shipped.
  #
  # Only in PR context. On the default branch — the cron `container-rescan`, and
  # an after-json run on a push to main — the unpinned default-branch lookup is
  # already the right one, so it is left untouched. It is also the more robust
  # one there: the cron's head_sha is the latest *ingested* main commit, which
  # may not have been collected yet, and pinning to it would resolve nothing and
  # silently stop the re-scan.
  json_args=()
  if [ -n "${LUNAR_COMPONENT_PR:-}" ]; then
    json_args=(--pr "$LUNAR_COMPONENT_PR")
    [ -n "${LUNAR_COMPONENT_GIT_SHA:-}" ] && json_args+=(--git-sha "$LUNAR_COMPONENT_GIT_SHA")
  fi

  # LUNAR_COMPONENT_ID and LUNAR_COMPONENT_PR are both injected by the Lunar
  # runtime — neither is a misspelling of the other.
  # shellcheck disable=SC2153
  COMPONENT_JSON=$(lunar component get-json "$LUNAR_COMPONENT_ID" "${json_args[@]}" 2>/dev/null || echo "")
  if [ -n "$COMPONENT_JSON" ]; then
    mapfile -t IMAGE_REFS < <(echo "$COMPONENT_JSON" | jq -r '
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
      | reduce .[] as $r ([]; if index($r) == null then . + [$r] else . end)
      | .[]
    ' 2>/dev/null || true)
  fi
fi

if [ "${#IMAGE_REFS[@]}" -eq 0 ]; then
  echo "No pushed container image to scan (no container_image input and no 'docker push' / '--push' build in .containers.native.docker.cicd.cmds[]) — skipping." >&2
  exit 0
fi

echo "Resolved ${#IMAGE_REFS[@]} image(s) to scan: ${IMAGE_REFS[*]}" >&2

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

# --- 3. Scan each image, normalizing as we go ---
WORK_DIR=$(mktemp -d /tmp/trivy-container.XXXXXX)
trap 'rm -rf "$WORK_DIR"' EXIT
IMAGES_FILE="$WORK_DIR/images.jsonl"   # one normalized object per scanned image, push order
ERRORS_FILE="$WORK_DIR/errors.jsonl"   # one {image, error} per image that could not be scanned
: > "$IMAGES_FILE"
: > "$ERRORS_FILE"
# The primary image — the most recently pushed one that scanned — keeps the
# single-image fields (`image`, `os`, raw native output) meaning what they
# always did.
PRIMARY_REF=""
PRIMARY_RESULTS=""
n=0
for IMAGE_REF in "${IMAGE_REFS[@]}"; do
  n=$((n + 1))
  echo "Scanning image: $IMAGE_REF" >&2
  RESULTS_FILE="$WORK_DIR/results-$n.json"
  STDERR_FILE="$WORK_DIR/stderr-$n.log"
  if ! trivy image --scanners vuln --format json "$IMAGE_REF" > "$RESULTS_FILE" 2>"$STDERR_FILE"; then
    echo "Trivy image scan failed for $IMAGE_REF — skipping this image." >&2
    cat "$STDERR_FILE" >&2 || true
    jq -nc --arg image "$IMAGE_REF" --rawfile err "$STDERR_FILE" \
      '{image: $image, error: ($err | gsub("\\s+$"; "") | .[0:500])}' >> "$ERRORS_FILE"
    continue
  fi

  # Normalize into the tool-agnostic .container_scan schema (mirrors auto.sh's
  # .sca normalization; adds image + os).
  jq -c --arg image "$IMAGE_REF" '
    def vulns: [.Results[]?.Vulnerabilities[]?];
    {
      image: $image,
      vulnerabilities: {
        critical: [vulns[] | select(.Severity == "CRITICAL")] | length,
        high:     [vulns[] | select(.Severity == "HIGH")]     | length,
        medium:   [vulns[] | select(.Severity == "MEDIUM")]   | length,
        low:      [vulns[] | select(.Severity == "LOW")]      | length,
        total:    (vulns | length)
      },
      findings: [.Results[]? as $r | $r.Vulnerabilities[]? | {
        severity:    (.Severity | ascii_downcase),
        package:     .PkgName,
        version:     .InstalledVersion,
        ecosystem:   $r.Type,
        cve:         .VulnerabilityID,
        title:       .Title,
        fix_version: (.FixedVersion // null),
        fixable:     (.FixedVersion != null and .FixedVersion != ""),
        image:       $image
      }],
      summary: {
        has_critical: ([vulns[] | select(.Severity == "CRITICAL")] | length > 0),
        has_high:     ([vulns[] | select(.Severity == "HIGH")]     | length > 0),
        all_fixable:  ([vulns[] | select(.FixedVersion == null or .FixedVersion == "")] | length == 0)
      }
    }
    + (if (.Metadata.OS.Family // "") != "" then
         {os: ({family: .Metadata.OS.Family} + (if (.Metadata.OS.Name // "") != "" then {version: .Metadata.OS.Name} else {} end))}
       else {} end)
  ' "$RESULTS_FILE" >> "$IMAGES_FILE"
  echo "Found $(jq '[.Results[]?.Vulnerabilities[]?] | length' "$RESULTS_FILE") vulnerabilities in $IMAGE_REF" >&2
  PRIMARY_REF="$IMAGE_REF"
  PRIMARY_RESULTS="$RESULTS_FILE"
done

if [ -z "$PRIMARY_REF" ]; then
  echo "Trivy could not scan any of the ${#IMAGE_REFS[@]} image(s) — skipping vulnerability collection." >&2
  exit 0
fi

# Preserve the primary image's raw Trivy results so policies can read fields we
# don't normalize. Per-image detail for every scanned image is in .findings[].image.
lunar collect -j ".container_scan.native.trivy.results" - < "$PRIMARY_RESULTS"

# Source metadata (integration set above: after-json on-push, or cron re-scan).
SOURCE_JSON=$(jq -n --arg version "$TRIVY_VERSION" --arg integration "$INTEGRATION" '{
  tool: "trivy",
  integration: $integration
} + (if $version != "" then {version: $version} else {} end)')

# --- 4. Aggregate ---
# `image` / `os` / raw native output describe the primary image, so a component
# that pushes one image sees exactly the shape it always did. Counts, summary and
# findings span every scanned image; images[] is the per-image breakdown and
# errors[] the refs that could not be pulled or scanned.
jq -c -s --argjson source "$SOURCE_JSON" --arg primary "$PRIMARY_REF" --slurpfile errors "$ERRORS_FILE" '
  . as $imgs
  | ($imgs | map(select(.image == $primary)) | last) as $p
  | ($imgs | map(.findings) | add) as $findings
  | {
      source: $source,
      image: $primary,
      images: ($imgs | map(
        {image: .image, tool: "trivy"}
        + (if .os then {os: .os} else {} end)
        + {vulnerabilities: .vulnerabilities, summary: .summary})),
      vulnerabilities: {
        critical: ($imgs | map(.vulnerabilities.critical) | add),
        high:     ($imgs | map(.vulnerabilities.high)     | add),
        medium:   ($imgs | map(.vulnerabilities.medium)   | add),
        low:      ($imgs | map(.vulnerabilities.low)      | add),
        total:    ($imgs | map(.vulnerabilities.total)    | add)
      },
      summary: {
        has_critical: ($imgs | any(.summary.has_critical)),
        has_high:     ($imgs | any(.summary.has_high)),
        all_fixable:  ($imgs | all(.summary.all_fixable))
      }
    }
  + (if ($findings | length) > 0 then {findings: $findings} else {} end)
  + (if $p.os then {os: $p.os} else {} end)
  + (if ($errors | length) > 0 then {errors: $errors} else {} end)
' "$IMAGES_FILE" | lunar collect -j ".container_scan" -

TOTAL=$(jq -s 'map(.vulnerabilities.total) | add' "$IMAGES_FILE")
echo "Found $TOTAL vulnerabilities across $(wc -l < "$IMAGES_FILE" | tr -d ' ') scanned image(s); $(wc -l < "$ERRORS_FILE" | tr -d ' ') could not be scanned" >&2
