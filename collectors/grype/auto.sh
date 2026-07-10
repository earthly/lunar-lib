#!/bin/bash
set -eo pipefail

echo "Running Grype vulnerability scan" >&2

# --- Scan-history preamble (opt-in; rescan/cron path only) -------------------
# This script is shared by the `auto` (code hook) and `rescan` (cron hook)
# sub-collectors (the cron one's name ends in "rescan", e.g. "grype.rescan").
# INTEGRATION stamps .sca.source so it's clear whether the data came from an
# on-push scan ("code") or a scheduled re-scan ("cron").
#
# With scan_history_size > 0 the rescan snapshots the current .sca into a
# bounded .sca.history[] before overwriting it (point-in-time audit), and
# max_rescans optionally caps the total number of re-scans. Both default 0 =
# today's overwrite-only behavior. Only the rescan path participates.
case "${LUNAR_COLLECTOR_NAME:-}" in
  *rescan) INTEGRATION="cron"; IS_RESCAN=true ;;
  *)       INTEGRATION="code"; IS_RESCAN=false ;;
esac

HIST_SIZE="${LUNAR_VAR_SCAN_HISTORY_SIZE:-0}"
MAX_RESCANS="${LUNAR_VAR_MAX_RESCANS:-0}"
case "$HIST_SIZE" in ''|*[!0-9]*) HIST_SIZE=0 ;; esac
case "$MAX_RESCANS" in ''|*[!0-9]*) MAX_RESCANS=0 ;; esac

# Read the current merged .sca once (feeds both history and max_rescans). If the
# read fails while history/max_rescans is enabled, SKIP the re-scan (exit 0)
# rather than overwrite .sca: latest-cron-per-collector replaces the prior cron
# record wholesale, so a new record missing history/rescan_count would wipe the
# accumulated audit trail this feature exists to preserve. Skipping keeps the
# last good record; the next tick retries. (The default path — both inputs 0 —
# never reads and never skips, so today's overwrite-only behavior is unchanged.)
CUR_SCA="{}"
if [ "$IS_RESCAN" = true ] && { [ "$HIST_SIZE" -gt 0 ] || [ "$MAX_RESCANS" -gt 0 ]; }; then
  RAW_JSON=""
  if [ -n "${LUNAR_COMPONENT_ID:-}" ] \
     && RAW_JSON=$(lunar component get-json "$LUNAR_COMPONENT_ID" 2>/dev/null) \
     && [ -n "$RAW_JSON" ] \
     && printf '%s' "$RAW_JSON" | jq -e . >/dev/null 2>&1; then
    CUR_SCA=$(printf '%s' "$RAW_JSON" | jq -c '.sca // {}')
  else
    echo "Scan history: could not read current component JSON (LUNAR_COMPONENT_ID unset or get-json failed) — skipping this re-scan to preserve existing .sca.history / rescan_count" >&2
    exit 0
  fi
  # max_rescans: stop re-scanning once the monotonic tally reaches the cap.
  if [ "$MAX_RESCANS" -gt 0 ]; then
    CUR_COUNT=$(printf '%s' "$CUR_SCA" | jq -r '.rescan_count // 0' 2>/dev/null || echo 0)
    case "$CUR_COUNT" in ''|*[!0-9]*) CUR_COUNT=0 ;; esac
    if [ "$CUR_COUNT" -ge "$MAX_RESCANS" ]; then
      echo "Scan history: max_rescans ($MAX_RESCANS) reached (rescan_count=$CUR_COUNT) — skipping re-scan" >&2
      exit 0
    fi
  fi
fi
# ---------------------------------------------------------------------------

# Grype scans the repository filesystem (dependency manifests + lockfiles) for
# known CVEs. `dir:.` catalogs packages across all supported ecosystems in one
# pass.
#
# DB source is controlled by the `db_auto_update` input (default false):
#   - false (default): scan against the DB pre-baked into the image (see
#     Earthfile), queried on-disk via SQLite — lighter, but only as fresh as the
#     image build. VALIDATE_AGE is off so a slightly-older image's DB isn't
#     rejected.
#   - true: download the current DB at scan time so the scan sees CVEs published
#     since the image was built. Grype's DB decompresses to ~1.7GB, so the
#     auto/rescan collectors declare `size: large` to give the container the
#     memory + ephemeral storage the runtime DB needs. Without that headroom the
#     download OOM-kills the collector (exit 137), so this requires a Hub that
#     honors collector size (ENG-983) — kept default-off until size-aware Hub
#     builds ship everywhere; flip back to true then.
if [ "${LUNAR_INPUT_DB_AUTO_UPDATE:-false}" = "true" ]; then
  export GRYPE_DB_CACHE_DIR=/var/tmp/lunar-grype-db
  # GRYPE_DB_AUTO_UPDATE defaults true → fresh DB each scan
else
  export GRYPE_DB_CACHE_DIR="${GRYPE_DB_CACHE_DIR:-/opt/grype/db}"
  export GRYPE_DB_AUTO_UPDATE=false
  export GRYPE_DB_VALIDATE_AGE=false
fi
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

# Build source metadata JSON. collected_at dates each scan so a snapshot pushed
# into .sca.history[] is self-describing — integration + timestamp identify the
# release-time "code" scan vs a scheduled "cron" re-scan.
COLLECTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
SOURCE_JSON=$(jq -n --arg version "$GRYPE_VERSION" --arg integration "$INTEGRATION" --arg collected_at "$COLLECTED_AT" '{
  tool: "grype",
  integration: $integration,
  collected_at: $collected_at
} + (if $version != "" then {version: $version} else {} end)')

# Build the .sca.history + rescan_count fragment, merged into the .sca write
# below via `+ $extra`. rescan_count is bumped whenever EITHER input is set, so
# max_rescans works standalone (no dependency on scan_history_size). The history
# array is maintained only when scan_history_size > 0. The prior scan is
# snapshotted as a compact {source, vulnerabilities, summary} entry — no
# findings/native (those arrays concatenate across the code+cron records, so
# snapshotting them would double and bloat) and no nested history. Only appended
# when there's a real prior scan ($snap != {}). latest-cron-per-collector keeps
# only this run's cron record, so .sca.history never self-concatenates.
HISTORY_JSON="{}"
if [ "$IS_RESCAN" = true ] && { [ "$HIST_SIZE" -gt 0 ] || [ "$MAX_RESCANS" -gt 0 ]; }; then
  HISTORY_JSON=$(printf '%s' "$CUR_SCA" | jq -c --argjson size "$HIST_SIZE" '
    (.history // []) as $hist
    | (.rescan_count // 0) as $count
    | ({source, vulnerabilities, summary} | with_entries(select(.value != null))) as $snap
    | (if ($size > 0 and $snap != {}) then ($hist + [$snap]) else $hist end) as $all
    | ($all | length) as $len
    | ({rescan_count: ($count + 1)}
       + (if $size > 0
          then {history: (if $len > $size then ([$all[0]] + $all[($len - ($size - 1)):]) else $all end)}
          else {} end))' 2>/dev/null || echo "{}")
  [ -n "$HISTORY_JSON" ] || HISTORY_JSON="{}"
fi

# Check if any vulnerabilities found
VULN_COUNT=$(jq '.matches | length' "$RESULTS_FILE")
if [ "$VULN_COUNT" = "0" ] || [ -z "$VULN_COUNT" ]; then
  echo "No vulnerabilities found" >&2
  # Write everything in a single collect call to avoid merge fragmentation
  jq -n --argjson source "$SOURCE_JSON" --argjson extra "$HISTORY_JSON" '{
    source: $source,
    vulnerabilities: {critical: 0, high: 0, medium: 0, low: 0, total: 0},
    summary: {has_critical: false, has_high: false, all_fixable: true}
  } + $extra' | lunar collect -j ".sca" -
  exit 0
fi

# Normalize into the tool-agnostic .sca schema.
# Grype severities are Critical/High/Medium/Low/Negligible/Unknown. The .sca
# schema has only critical/high/medium/low buckets, so:
#   - Negligible folds into `low` (both in counts and in finding severity)
#   - Unknown has no bucket but still counts toward `total`
# fixable = (fix.state == "fixed"); fix_version = first fixed version.
jq -c --argjson source "$SOURCE_JSON" --argjson extra "$HISTORY_JSON" '
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
  } + $extra' "$RESULTS_FILE" | lunar collect -j ".sca" -

echo "Found $VULN_COUNT vulnerabilities" >&2
