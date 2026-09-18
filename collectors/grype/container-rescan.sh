#!/bin/bash
set -eo pipefail

# Scan every container image this component shipped and write normalized,
# per-image results to .container_scan.
#
# Shared by two sub-collectors: the on-push `container-scan` (after-json hook)
# and the scheduled `container-rescan` (cron). Both run in the Grype collector
# image (baked-in DB), no code clone. The images are resolved from the docker
# collector's pushed-image record (.containers.native.docker.cicd.cmds[]) via
# `lunar component get-json`, or pinned with the `container_image` input. Only
# source.integration differs between the two.

echo "Running Grype container image scan" >&2

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
# Bookkeeping for the skip-vs-fail decision at the end of this section, so it is
# total: `pinned` means the container_image input supplied the refs and no Hub
# read ever happened.
RESOLVE_STATE=pinned
ATTEMPT=0
WAITED=0
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

  # The refs this component SHIPPED, in push order, the same ref twice counting
  # once. Reads a Component JSON blob on stdin.
  pushed_image_refs() {
    jq -r '
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
    '
  }

  # The read races the record that dispatched this run, so it is RETRIED.
  #
  # The after-json wave fires off the LIVE hub.merged_collection_blobs row the
  # instant the push record lands, but `lunar component get-json` resolves
  # through public.components[_latest] -> mat.component_json — a copy the Hub's
  # mat workers drain asynchronously. So this collector can be dispatched by a
  # record it cannot yet read, and sha-pinning does not help: a pinned read goes
  # through the same mat copy.
  #
  # Measured on an internal Hub, 12 days, 452 container-scan waves on one
  # component: 66 shas had a push record that landed BEFORE the run started and
  # still scanned nothing. Those runs started a median 31s (max 112s) after the
  # push record, while the runs that did resolve started a median 93s after it.
  #
  # Two failure shapes, kept apart on purpose — conflating them is the defect
  # this fixes. Previously both ended at the same silent `exit 0`, so "nothing
  # was pushed" and "I could not find out" were indistinguishable.
  #
  #   read returns nothing      This sha's row has not materialized. Retry for
  #                             READ_BUDGET_SECS, then FAIL the run. The wave is
  #                             fire-once per (component, sha) — Gate.Pending
  #                             enqueues only when not already dispatched, and
  #                             the job is unique ByArgs — so a swallowed read
  #                             loses this commit's scan permanently and no
  #                             re-run recovers it. Waiting beats losing it.
  #                             900s follows collectors/codeql/monorepo-fanout.sh,
  #                             which measured this same mat lag at 195/255/285
  #                             and 292+s and found 300s to be the boundary.
  #
  #   read OK, no pushed ref    Either the push record has not drained yet (the
  #                             race above) or this commit genuinely shipped
  #                             nothing. A collector cannot tell those apart:
  #                             the hook fires on
  #                             .containers.native.docker.cicd.cmds, which the
  #                             docker collector writes for ANY traced docker
  #                             command, so "docker ran" is enough to dispatch a
  #                             wave — 169 of those 452 waves never had a push
  #                             record at all. So retry only long enough to
  #                             cover the measured race (max 112s) with
  #                             headroom, then exit 0 saying plainly that the
  #                             read succeeded and no ref appeared. Failing here
  #                             would redden 37% of waves for a legitimate state.
  #
  # The cron re-scan is not dispatched off a record, so it has no race to lose
  # to, and it runs again on the next tick — it gets a short read retry, never
  # waits for a ref to appear, and never fails the run.
  #
  # The _TEST_ overrides are a test seam, deliberately NOT declared in `inputs:`
  # — they are not part of the plugin's config surface and cannot be set with
  # `with:`. Without them the suite would sit here for the full budget.
  if [ "$INTEGRATION" = "after-json" ]; then
    READ_BUDGET_SECS="${LUNAR_CONTAINER_SCAN_TEST_READ_BUDGET:-900}"
    RESOLVE_BUDGET_SECS="${LUNAR_CONTAINER_SCAN_TEST_RESOLVE_BUDGET:-180}"
  else
    READ_BUDGET_SECS="${LUNAR_CONTAINER_SCAN_TEST_READ_BUDGET:-30}"
    RESOLVE_BUDGET_SECS=0
  fi
  # Linear backoff, BACKOFF_STEP per attempt, capped at 6 steps: 5s, 10s, 15s
  # ... 30s, 30s. Same seam as the budgets above, so the suite exercises the
  # real loop without sleeping for real.
  BACKOFF_STEP="${LUNAR_CONTAINER_SCAN_TEST_BACKOFF_STEP:-5}"

  # Disposable container, so a fixed path needs no mktemp and no cleanup.
  GETJSON_ERR=/tmp/get-json.err

  # LUNAR_COMPONENT_ID and LUNAR_COMPONENT_PR are both injected by the Lunar
  # runtime — neither is a misspelling of the other.
  # shellcheck disable=SC2153
  while :; do
    ATTEMPT=$((ATTEMPT + 1))
    if COMPONENT_JSON=$(lunar component get-json "$LUNAR_COMPONENT_ID" "${json_args[@]}" 2>"$GETJSON_ERR") \
       && [ -n "$COMPONENT_JSON" ]; then
      RESOLVE_STATE=no_refs
      BUDGET="$RESOLVE_BUDGET_SECS"
      # jq's stderr is NOT silenced: a blob that fails to parse is a real
      # problem, and hiding it was one of the layers that made this silent.
      mapfile -t IMAGE_REFS < <(printf '%s' "$COMPONENT_JSON" | pushed_image_refs)
      [ "${#IMAGE_REFS[@]}" -gt 0 ] && break
    else
      COMPONENT_JSON=""
      RESOLVE_STATE=read_failed
      BUDGET="$READ_BUDGET_SECS"
      # Surface the CLI's own error instead of discarding it. Once, not once per
      # attempt.
      if [ "$ATTEMPT" -eq 1 ] && [ -s "$GETJSON_ERR" ]; then
        # The error itself, not cobra's usage block — the CLI prints ~18 lines
        # of flags after it on any failure, which would bury the run log.
        sed -n '/^Usage:/q;p' "$GETJSON_ERR" | head -c 500 | sed 's/^/  get-json: /' >&2
      fi
    fi
    BACKOFF=$((ATTEMPT * BACKOFF_STEP))
    [ "$BACKOFF" -gt $((BACKOFF_STEP * 6)) ] && BACKOFF=$((BACKOFF_STEP * 6))
    [ $((WAITED + BACKOFF)) -gt "$BUDGET" ] && break
    sleep "$BACKOFF"
    WAITED=$((WAITED + BACKOFF))
  done
  if [ "$WAITED" -gt 0 ]; then
    echo "Waited ${WAITED}s across ${ATTEMPT} attempt(s) for the pushed-image record to become readable." >&2
  fi
fi

if [ "${#IMAGE_REFS[@]}" -eq 0 ]; then
  case "$RESOLVE_STATE" in
    read_failed)
      # Distinguishable from a genuine no-push, and fatal on the fire-once leg.
      echo "Could not read Component JSON for ${LUNAR_COMPONENT_ID:-?} after ${WAITED}s across ${ATTEMPT} attempt(s) — see the get-json error above. This commit's row has most likely not materialized yet (mat.component_json drains asynchronously, so the read lags the record that dispatched this run)." >&2
      if [ "$INTEGRATION" = "after-json" ]; then
        echo "Failing the run: the after-json wave is fire-once per (component, sha), so this commit's container scan is lost and no re-run recovers it. Push a new commit once the Hub catches up." >&2
        exit 1
      fi
      echo "Skipping this re-scan; the next scheduled run will try again." >&2
      exit 0
      ;;
    pinned)
      echo "No container image to scan: the container_image input is set but resolved to no reference — skipping." >&2
      exit 0
      ;;
    *)
      echo "No pushed container image to scan: read the Component JSON for ${LUNAR_COMPONENT_ID:-?} successfully and found no 'docker push' / '--push' build in .containers.native.docker.cicd.cmds[], and no container_image input — skipping." >&2
      exit 0
      ;;
  esac
fi

echo "Resolved ${#IMAGE_REFS[@]} image(s) to scan: ${IMAGE_REFS[*]}" >&2

# --- 2. Registry auth for private images (optional) ---
# Grype/Stereoscope reads registry credentials from these env vars. Public
# images need none. The username is accepted under either REGISTRY_USERNAME or
# REGISTRY_USER — both are common registry/CI conventions, so match whatever the
# deployer already has configured rather than forcing one spelling.
REG_USER="${LUNAR_SECRET_REGISTRY_USERNAME:-${LUNAR_SECRET_REGISTRY_USER:-}}"
if [ -n "$REG_USER" ] && [ -n "${LUNAR_SECRET_REGISTRY_PASSWORD:-}" ]; then
  export GRYPE_REGISTRY_AUTH_USERNAME="$REG_USER"
  export GRYPE_REGISTRY_AUTH_PASSWORD="$LUNAR_SECRET_REGISTRY_PASSWORD"
fi

# Scan against the DB baked into the image (same default as auto.sh).
export GRYPE_DB_CACHE_DIR="${GRYPE_DB_CACHE_DIR:-/opt/grype/db}"
export GRYPE_DB_AUTO_UPDATE=false
export GRYPE_DB_VALIDATE_AGE=false
export GOGC=40

# --- 3. Scan each image, normalizing as we go ---
WORK_DIR=$(mktemp -d /tmp/grype-container.XXXXXX)
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
  if ! grype "$IMAGE_REF" -o json > "$RESULTS_FILE" 2>"$STDERR_FILE"; then
    echo "Grype image scan failed for $IMAGE_REF — skipping this image." >&2
    cat "$STDERR_FILE" >&2 || true
    jq -nc --arg image "$IMAGE_REF" --rawfile err "$STDERR_FILE" \
      '{image: $image, error: ($err | gsub("\\s+$"; "") | .[0:500])}' >> "$ERRORS_FILE"
    continue
  fi

  # Normalize into the tool-agnostic .container_scan schema (mirrors auto.sh's
  # .sca normalization; adds image + os). Negligible folds into low; Unknown
  # still counts toward total.
  jq -c --arg image "$IMAGE_REF" '
    def matches: (.matches // []);
    def sev: (.vulnerability.severity // "Unknown") | ascii_downcase;
    {
      image: $image,
      vulnerabilities: {
        critical: [matches[] | select(sev == "critical")] | length,
        high:     [matches[] | select(sev == "high")]     | length,
        medium:   [matches[] | select(sev == "medium")]   | length,
        low:      [matches[] | select(sev == "low" or sev == "negligible")] | length,
        total:    (matches | length)
      },
      findings: [matches[] | {
        severity:    (if sev == "negligible" then "low" else sev end),
        package:     .artifact.name,
        version:     .artifact.version,
        ecosystem:   .artifact.type,
        cve:         .vulnerability.id,
        title:       (.vulnerability.description // null),
        fix_version: ((.vulnerability.fix.versions // [])[0] // null),
        fixable:     (.vulnerability.fix.state == "fixed"),
        image:       $image
      }],
      summary: {
        has_critical: ([matches[] | select(sev == "critical")] | length > 0),
        has_high:     ([matches[] | select(sev == "high")]     | length > 0),
        all_fixable:  ([matches[] | select(.vulnerability.fix.state != "fixed")] | length == 0)
      }
    }
    + (if (.distro.name // "") != "" then
         {os: ({family: .distro.name} + (if (.distro.version // "") != "" then {version: .distro.version} else {} end))}
       else {} end)
  ' "$RESULTS_FILE" >> "$IMAGES_FILE"
  echo "Found $(jq '(.matches // []) | length' "$RESULTS_FILE") vulnerabilities in $IMAGE_REF" >&2
  PRIMARY_REF="$IMAGE_REF"
  PRIMARY_RESULTS="$RESULTS_FILE"
done

if [ -z "$PRIMARY_REF" ]; then
  echo "Grype could not scan any of the ${#IMAGE_REFS[@]} image(s) — skipping vulnerability collection." >&2
  exit 0
fi

GRYPE_VERSION=$(jq -r '.descriptor.version // empty' "$PRIMARY_RESULTS")

# Preserve the primary image's raw matches so policies can read fields we don't
# normalize. Per-image detail for every scanned image is in .findings[].image.
jq -c '.matches // []' "$PRIMARY_RESULTS" | lunar collect -j ".container_scan.native.grype.matches" -

# Source metadata (integration set above: after-json on-push, or cron re-scan).
SOURCE_JSON=$(jq -n --arg version "$GRYPE_VERSION" --arg integration "$INTEGRATION" '{
  tool: "grype",
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
        {image: .image, tool: "grype"}
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
