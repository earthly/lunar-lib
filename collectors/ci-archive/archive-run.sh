#!/bin/bash
set -eo pipefail

# Archive one finished GitHub Actions run attempt (metadata plus the full log
# archive) to S3, then record where it went under .ci.archive.runs[] on the
# commit that run built.
#
# Two callers, one per finished run attempt, re-runs included:
#   - the GitHub Action, in a workflow on `workflow_run: completed`, with AWS
#     credentials from the job (OIDC), so the bucket never has to trust Lunar;
#   - workflow-logs.sh, the collector the Hub runs on its workflow-end hook.

log() { echo "ci-archive: $*" >&2; }

S3_BUCKET="${CI_ARCHIVE_S3_BUCKET:-}"
S3_PREFIX="${CI_ARCHIVE_S3_PREFIX-lunar/ci-archive}"
S3_ENDPOINT_URL="${CI_ARCHIVE_S3_ENDPOINT_URL:-}"
REGION="${CI_ARCHIVE_AWS_REGION:-${AWS_REGION:-${AWS_DEFAULT_REGION:-}}}"
MAX_ARCHIVE_MB="${CI_ARCHIVE_MAX_ARCHIVE_MB:-512}"
RECORD="${CI_ARCHIVE_RECORD_IN_LUNAR:-true}"
INTEGRATION="${CI_ARCHIVE_INTEGRATION:-github-action}"
INCLUDE_EVENTS="${CI_ARCHIVE_INCLUDE_EVENTS:-}"
EVENT_PATH="${GITHUB_EVENT_PATH:-}"
RUN_ID="${CI_ARCHIVE_RUN_ID:-}"
ATTEMPT="${CI_ARCHIVE_RUN_ATTEMPT:-}"
REPO="${CI_ARCHIVE_REPOSITORY:-}"

if [ -n "$EVENT_PATH" ] && [ -f "$EVENT_PATH" ] && jq -e '.workflow_run' "$EVENT_PATH" >/dev/null 2>&1; then
  RUN_ID="${RUN_ID:-$(jq -r '.workflow_run.id' "$EVENT_PATH")}"
  ATTEMPT="${ATTEMPT:-$(jq -r '.workflow_run.run_attempt' "$EVENT_PATH")}"
  REPO="${REPO:-$(jq -r '.workflow_run.repository.full_name' "$EVENT_PATH")}"
fi
REPO="${REPO:-${GITHUB_REPOSITORY:-}}"
ATTEMPT="${ATTEMPT:-1}"

[ -n "$S3_BUCKET" ] || { log "ERROR: the s3-bucket input is required."; exit 1; }
[ -n "$RUN_ID" ] || { log "ERROR: no run to archive: trigger on workflow_run or set run-id."; exit 1; }
[ -n "$REPO" ] || { log "ERROR: could not tell which repository the run belongs to."; exit 1; }
[ -n "${GH_TOKEN:-}" ] || { log "ERROR: GH_TOKEN is empty; the job needs actions: read."; exit 1; }
[ -n "$REGION" ] || { log "ERROR: no AWS region: set aws-region or configure AWS credentials first."; exit 1; }
if [ -z "${AWS_ACCESS_KEY_ID:-}" ] || [ -z "${AWS_SECRET_ACCESS_KEY:-}" ]; then
  log "ERROR: no AWS credentials in the environment. Run aws-actions/configure-aws-credentials first."
  exit 1
fi
if ! [[ "$MAX_ARCHIVE_MB" =~ ^[0-9]+$ ]] || [ "$MAX_ARCHIVE_MB" -eq 0 ]; then
  log "ERROR: max-archive-mb must be a positive integer, got '${MAX_ARCHIVE_MB}'."
  exit 1
fi
MAX_BYTES=$((MAX_ARCHIVE_MB * 1024 * 1024))

SERVER_URL="${GITHUB_SERVER_URL:-https://github.com}"
HOST="${SERVER_URL#*://}"; HOST="${HOST%%/*}"
API_BASE="${GITHUB_API_URL:-https://api.github.com}"
COMPONENTS="${CI_ARCHIVE_COMPONENTS:-${HOST}/${REPO}}"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
file_size() { wc -c < "$1" | tr -d ' '; }

# gh_get <path> <outfile> prints the HTTP status; retries connection
# failures, 429 and 5xx.
gh_get() {
  local code attempt=0
  while :; do
    attempt=$((attempt + 1))
    code=$(curl -sS -o "$2" -w '%{http_code}' --max-time 60 \
      -H "Accept: application/vnd.github+json" \
      -H "Authorization: Bearer ${GH_TOKEN}" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      "${API_BASE}/repos/${REPO}/$1" 2>/dev/null) || code="000"
    case "$code" in
      000|429|5??) if [ "$attempt" -lt 3 ]; then sleep $((attempt * 2)); continue; fi ;;
    esac
    printf '%s' "$code"
    return 0
  done
}

# --- 1. The run attempt and its jobs ---
code=$(gh_get "actions/runs/${RUN_ID}/attempts/${ATTEMPT}" "$WORK/run.json")
[ "$code" = "200" ] || { log "ERROR: reading run ${RUN_ID} attempt ${ATTEMPT} returned HTTP ${code}."; exit 1; }
EVENT=$(jq -r '.event' "$WORK/run.json")
# Commas or whitespace separate the events.
if [ -n "$INCLUDE_EVENTS" ] && [[ ",${INCLUDE_EVENTS//[[:space:]]/,}," != *",${EVENT},"* ]]; then
  log "run ${RUN_ID} was triggered by ${EVENT}, not one of the included events (${INCLUDE_EVENTS}); skipping."
  exit 0
fi
STATUS=$(jq -r '.status' "$WORK/run.json")
[ "$STATUS" = "completed" ] || { log "ERROR: run ${RUN_ID} attempt ${ATTEMPT} is ${STATUS}, not completed."; exit 1; }
# The Hub hands a workflow-end collector the commit the run's chain started
# from, which for a run another workflow started isn't the one GitHub recorded.
SHA="${CI_ARCHIVE_SHA:-$(jq -r '.head_sha' "$WORK/run.json")}"
PR=""
case "$EVENT" in
  pull_request|pull_request_target) PR=$(jq -r '.pull_requests[0].number // empty' "$WORK/run.json") ;;
esac

echo '[]' > "$WORK/jobs.json"
page=1
while :; do
  code=$(gh_get "actions/runs/${RUN_ID}/attempts/${ATTEMPT}/jobs?per_page=100&page=${page}" "$WORK/page.json")
  [ "$code" = "200" ] || { log "ERROR: listing jobs returned HTTP ${code}."; exit 1; }
  jq -s '.[0] + [.[1].jobs[] | {id, name, conclusion, started_at, completed_at, html_url,
          steps: [(.steps // [])[] | {number, name, conclusion}]}]' \
    "$WORK/jobs.json" "$WORK/page.json" > "$WORK/jobs.tmp" && mv "$WORK/jobs.tmp" "$WORK/jobs.json"
  [ "$(jq '.jobs | length' "$WORK/page.json")" -lt 100 ] && break
  page=$((page + 1))
done

# --- 2. The attempt's log archive ---
# GitHub creates a job's log only when the job completes, so allow a short
# lag after the run finishes. The 302 target is fetched without the token.
code=""; loc=""
for attempt in 1 2 3 4 5 6; do
  out=$(curl -sS -o /dev/null -w '%{http_code} %{redirect_url}' --max-time 60 \
    -H "Accept: application/vnd.github+json" \
    -H "Authorization: Bearer ${GH_TOKEN}" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "${API_BASE}/repos/${REPO}/actions/runs/${RUN_ID}/attempts/${ATTEMPT}/logs" 2>/dev/null) || out="000 "
  code="${out%% *}"; loc="${out#* }"
  case "$code" in 000|404|429|5??) sleep $((attempt * 5)); continue ;; esac
  break
done
[ "$code" = "302" ] || { log "ERROR: downloading logs for run ${RUN_ID} attempt ${ATTEMPT} returned HTTP ${code}."; exit 1; }
status=0
curl -sS -f -o "$WORK/logs.zip" --max-time 900 --retry 2 --max-filesize "$MAX_BYTES" "$loc" 2>/dev/null || status=$?
if [ "$status" -eq 63 ]; then
  log "ERROR: the log archive is over max-archive-mb (${MAX_ARCHIVE_MB} MB); nothing uploaded."
  exit 1
elif [ "$status" -ne 0 ]; then
  log "ERROR: log archive download failed (curl exit ${status})."
  exit 1
fi
LOG_BYTES=$(file_size "$WORK/logs.zip")

# --- 3. Bundle and upload ---
ARCHIVED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
jq -n --arg repo "$REPO" --arg sha "$SHA" --arg at "$ARCHIVED_AT" --argjson bytes "$LOG_BYTES" \
  --arg triggered_by "${CI_ARCHIVE_TRIGGERED_BY_RUN_ID:-}" --arg origin "${CI_ARCHIVE_ORIGIN_SOURCE:-}" \
  --slurpfile run "$WORK/run.json" --slurpfile jobs "$WORK/jobs.json" '
  ($run[0]) as $r | {
    repository: $repo, sha: $sha, archived_at: $at,
    run: ({id: $r.id, attempt: $r.run_attempt, name: $r.name, path: $r.path, event: $r.event,
          head_branch: $r.head_branch, head_sha: $r.head_sha, conclusion: $r.conclusion,
          started_at: $r.run_started_at, completed_at: $r.updated_at, html_url: $r.html_url, log_bytes: $bytes}
          + (if $triggered_by == "" then {} else {triggered_by_run_id: $triggered_by} end)
          + (if $origin == "" then {} else {origin_source: $origin} end)),
    jobs: $jobs[0]
  }' > "$WORK/manifest.json"
python3 - "$WORK/archive.zip" "$WORK/manifest.json" "$WORK/logs.zip" <<'PY'
import sys, zipfile
archive, manifest, logs = sys.argv[1:4]
with zipfile.ZipFile(archive, "w", allowZip64=True) as zf:
    zf.write(manifest, "manifest.json", compress_type=zipfile.ZIP_DEFLATED)
    zf.write(logs, "logs.zip", compress_type=zipfile.ZIP_STORED)
PY

prefix="${S3_PREFIX#/}"; prefix="${prefix%/}"
KEY="${HOST}/${REPO}/${SHA}/${RUN_ID}-${ATTEMPT}.zip"
[ -n "$prefix" ] && KEY="${prefix}/${KEY}"
KEY="$(printf '%s' "$KEY" | tr -c 'A-Za-z0-9._/-' '_')"
if [ -n "$S3_ENDPOINT_URL" ]; then
  URL="${S3_ENDPOINT_URL%/}/${S3_BUCKET}/${KEY}"
elif [[ "$S3_BUCKET" == *.* ]]; then
  URL="https://s3.${REGION}.amazonaws.com/${S3_BUCKET}/${KEY}"
else
  URL="https://${S3_BUCKET}.s3.${REGION}.amazonaws.com/${KEY}"
fi

SIZE=$(file_size "$WORK/archive.zip")
PAYLOAD_SHA=$(sha256sum "$WORK/archive.zip" | cut -d' ' -f1)
token_hdr=()
[ -n "${AWS_SESSION_TOKEN:-}" ] && token_hdr=(-H "x-amz-security-token: ${AWS_SESSION_TOKEN}")
code=""
for attempt in 1 2 3; do
  code=$(curl -sS -o "$WORK/s3.out" -w '%{http_code}' --max-time 1800 -X PUT \
    --aws-sigv4 "aws:amz:${REGION}:s3" \
    --user "${AWS_ACCESS_KEY_ID}:${AWS_SECRET_ACCESS_KEY}" \
    "${token_hdr[@]}" \
    -H "x-amz-content-sha256: ${PAYLOAD_SHA}" \
    -H "Content-Type: application/zip" \
    -T "$WORK/archive.zip" "$URL" 2>/dev/null) || code="000"
  case "$code" in 000|429|5??) sleep $((attempt * 2)); continue ;; esac
  break
done
if [ "$code" != "200" ]; then
  s3_code=$(sed -n 's:.*<Code>\(.*\)</Code>.*:\1:p' "$WORK/s3.out" 2>/dev/null | head -1)
  log "ERROR: S3 upload to s3://${S3_BUCKET}/${KEY} failed: HTTP ${code}${s3_code:+ ($s3_code)}."
  exit 1
fi
URI="s3://${S3_BUCKET}/${KEY}"
log "uploaded ${URI} (${SIZE} bytes) for $(jq -r '.name' "$WORK/run.json") run ${RUN_ID} attempt ${ATTEMPT}."
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  { echo "uri=${URI}"; echo "sha=${SHA}"; } >> "$GITHUB_OUTPUT"
fi

# --- 4. Record the receipt on the archived commit ---
if [ "$RECORD" != "true" ]; then
  exit 0
fi
command -v lunar >/dev/null 2>&1 || { log "ERROR: the lunar CLI is not on PATH; set record-in-lunar: false to skip."; exit 1; }
BY=""
[ -n "${GITHUB_RUN_ID:-}" ] && BY="${SERVER_URL}/${GITHUB_REPOSITORY:-$REPO}/actions/runs/${GITHUB_RUN_ID}"
jq -n --arg uri "$URI" --arg bucket "$S3_BUCKET" --arg key "$KEY" --argjson size "$SIZE" \
  --arg at "$ARCHIVED_AT" --arg integration "$INTEGRATION" --arg by "$BY" \
  --slurpfile m "$WORK/manifest.json" '
  $m[0].run + {uri: $uri, bucket: $bucket, key: $key, size_bytes: $size,
    jobs: [$m[0].jobs[] | {name, conclusion}],
    source: ({tool: "ci-archive", integration: $integration, collected_at: $at}
             + (if $by == "" then {} else {archived_by: $by} end))}' \
  > "$WORK/receipt.json"
# Inside a Lunar collector the write lands on the component and commit the
# collector runs for, which are the ones this run built.
if [ -n "${LUNAR_COLLECT_STDOUT:-}" ]; then
  lunar collect --json --array-append ".ci.archive.runs" - < "$WORK/receipt.json"
  exit 0
fi
for component in $COMPONENTS; do
  pr_args=()
  [ -n "$PR" ] && pr_args=(--pr "$PR")
  lunar collect --component "$component" --sha "$SHA" "${pr_args[@]}" \
    --json --array-append ".ci.archive.runs" - < "$WORK/receipt.json"
  log "recorded ${URI} on ${component}@${SHA}${PR:+ (PR #${PR})}."
done
