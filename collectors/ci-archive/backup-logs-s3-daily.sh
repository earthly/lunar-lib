#!/bin/bash
set -eo pipefail

# The daily backup behind backup-logs-s3: list the default branch's finished
# workflow runs created in the last daily_backup_lookback_hours, and upload
# every run attempt whose object isn't in the bucket yet, under the key
# backup-logs-s3 uses. Writes a summary of the pass to .ci.archive.backup.

log() { echo "ci-archive: $*" >&2; }
uri() { jq -rn --arg s "$1" '$s|@uri'; }
iso() { jq -rn --argjson t "$1" '$t|todate'; }

S3_BUCKET="${LUNAR_VAR_S3_BUCKET:-}"
S3_PREFIX="${LUNAR_VAR_S3_PREFIX-lunar/ci-archive}"
S3_ENDPOINT_URL="${LUNAR_VAR_S3_ENDPOINT_URL:-}"
INCLUDE_RUNS_PATTERN="${LUNAR_VAR_INCLUDE_RUNS_PATTERN:-}"
INCLUDE_EVENTS="${LUNAR_VAR_INCLUDE_EVENTS:-}"
LOOKBACK_INPUT="${LUNAR_VAR_DAILY_BACKUP_LOOKBACK_HOURS:-48}"
BRANCH="${LUNAR_VAR_DAILY_BACKUP_BRANCH:-}"

if [ -z "${LUNAR_SECRET_GH_TOKEN:-}" ]; then
  log "GH_TOKEN secret is not set; skipping."
  exit 0
fi

# Component IDs are <host>/<owner>/<repository>[/<subpath>...]. Only the
# repository's root component backs it up, so a monorepo's runs are fetched once.
IFS=/ read -r HOST OWNER NAME SUBPATH <<< "${LUNAR_COMPONENT_ID:-}"
if [ -z "$NAME" ] || [ -n "$SUBPATH" ]; then
  log "${LUNAR_COMPONENT_ID:-this component} is not a repository's root component, which is the one that backs up its runs. Skipping."
  exit 0
fi
REPO="${OWNER}/${NAME}"
case "$HOST" in
  *gitlab*) log "GitHub Actions only; ${HOST} is not supported. Skipping."; exit 0 ;;
esac
API_BASE="https://api.github.com"
if [ "$HOST" != "github.com" ]; then
  API_BASE="https://${HOST}/api/v3"
fi

case "$LOOKBACK_INPUT" in
  ''|*[!0-9]*|??????*) LOOKBACK=0 ;;
  *) LOOKBACK=$((10#$LOOKBACK_INPUT)) ;;
esac
if [ "$LOOKBACK" -le 0 ]; then
  log "ERROR: daily_backup_lookback_hours must be a positive whole number of hours, got '${LOOKBACK_INPUT}'."
  exit 1
fi
if [ -n "$INCLUDE_RUNS_PATTERN" ] && ! jq -n --arg re "$INCLUDE_RUNS_PATTERN" '"" | test($re)' >/dev/null 2>&1; then
  log "ERROR: include_runs_pattern is not a valid regex: ${INCLUDE_RUNS_PATTERN}"
  exit 1
fi

WORK="$(mktemp -d)"

# gh_get <path> <outfile> prints the HTTP status; retries connection
# failures, 429 and 5xx.
gh_get() {
  local code attempt=0
  while :; do
    attempt=$((attempt + 1))
    code=$(curl -sS -o "$2" -w '%{http_code}' --max-time 60 \
      -H "Accept: application/vnd.github+json" \
      -H "Authorization: Bearer ${LUNAR_SECRET_GH_TOKEN}" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      "${API_BASE}/$1" 2>/dev/null) || code="000"
    case "$code" in
      000|429|5??) if [ "$attempt" -lt 3 ]; then sleep $((attempt * 2)); continue; fi ;;
    esac
    printf '%s' "$code"
    return 0
  done
}

if [ -z "$BRANCH" ]; then
  code=$(gh_get "repos/${REPO}" "$WORK/repo.json")
  [ "$code" = "200" ] || { log "ERROR: reading repository ${REPO} returned HTTP ${code}."; exit 1; }
  BRANCH=$(jq -r '.default_branch' "$WORK/repo.json")
fi

# --- 1. The window's finished runs ---
UNTIL=$(date -u +%s)
SINCE=$((UNTIL - LOOKBACK * 3600))
: > "$WORK/runs.jsonl"
# GitHub returns nothing past the first 1,000 runs of a filtered list, so a
# slice holding that many is halved until each one fits.
slices=("${SINCE}:${UNTIL}")
while [ "${#slices[@]}" -gt 0 ]; do
  from="${slices[0]%%:*}"; to="${slices[0]##*:}"
  slices=("${slices[@]:1}")
  page=1
  while [ "$page" -le 10 ]; do
    code=$(gh_get "repos/${REPO}/actions/runs?branch=$(uri "$BRANCH")&status=completed&created=$(iso "$from")..$(iso "$to")&exclude_pull_requests=true&per_page=100&page=${page}" "$WORK/page.json")
    [ "$code" = "200" ] || { log "ERROR: listing workflow runs on ${BRANCH} returned HTTP ${code}."; exit 1; }
    if [ "$page" -eq 1 ] && [ "$(jq '.total_count' "$WORK/page.json")" -ge 1000 ] && [ "$to" -gt "$from" ]; then
      mid=$(( (from + to) / 2 ))
      slices+=("${from}:${mid}" "$((mid + 1)):${to}")
      break
    fi
    jq -c '.workflow_runs[] | {id, run_attempt, name, event, head_sha}' "$WORK/page.json" >> "$WORK/runs.jsonl"
    [ "$(jq '.workflow_runs | length' "$WORK/page.json")" -lt 100 ] && break
    page=$((page + 1))
  done
done

# One line per run attempt: run id, attempt, commit, workflow name.
jq -rs --arg re "$INCLUDE_RUNS_PATTERN" --arg events "$INCLUDE_EVENTS" '
  ($events | gsub("\\s+"; ",") | split(",") | map(select(. != ""))) as $ev
  | unique_by(.id)[]
  | select($re == "" or (.name | test($re)))
  | select(($ev | length) == 0 or (.event as $e | $ev | index($e)))
  | . as $r | range(1; $r.run_attempt + 1)
  | [$r.id, ., $r.head_sha, $r.name] | @tsv' "$WORK/runs.jsonl" > "$WORK/attempts.tsv"
ATTEMPTS=$(wc -l < "$WORK/attempts.tsv" | tr -d ' ')
WINDOW="${BRANCH} since $(iso "$SINCE")"

summary() { # summary [uploaded-count]
  jq -n --arg branch "$BRANCH" --arg since "$(iso "$SINCE")" --arg until "$(iso "$UNTIL")" \
    --argjson attempts "$ATTEMPTS" --arg uploaded "${1:-}" --arg at "$(iso "$(date -u +%s)")" '
    {branch: $branch, since: $since, until: $until, attempt_count: $attempts}
    + (if $uploaded == "" then {} else {uploaded_count: ($uploaded | tonumber)} end)
    + {source: {tool: "ci-archive", integration: "cron", collected_at: $at}}' \
    | lunar collect -j ".ci.archive.backup" -
}

if [ -z "$S3_BUCKET" ]; then
  log "s3_bucket is not set: found ${ATTEMPTS} run attempt(s) on ${WINDOW}; uploading nothing."
  summary
  exit 0
fi

# --- 2. What the bucket already holds ---
# shellcheck source=/dev/null
source "$(dirname "$0")/aws-credentials.sh"
s3_region || exit 1
s3_credentials "lunar-ci-archive-daily" || exit 1

prefix="${S3_PREFIX#/}"; prefix="${prefix%/}"
repo_prefix="${HOST}/${REPO}"
[ -n "$prefix" ] && repo_prefix="${prefix}/${repo_prefix}"
repo_prefix="$(printf '%s' "$repo_prefix" | tr -c 'A-Za-z0-9._/-' '_')"
if [ -n "$S3_ENDPOINT_URL" ]; then
  BUCKET_URL="${S3_ENDPOINT_URL%/}/${S3_BUCKET}"
elif [[ "$S3_BUCKET" == *.* ]]; then
  BUCKET_URL="https://s3.${REGION}.amazonaws.com/${S3_BUCKET}"
else
  BUCKET_URL="https://${S3_BUCKET}.s3.${REGION}.amazonaws.com/"
fi
log "checking s3://${S3_BUCKET}/${repo_prefix}/ (${REGION}) with AWS credentials from ${CRED_SOURCE}."

# s3_list <prefix> appends the name of each object under prefix to
# $WORK/present, following ListObjectsV2 pagination.
s3_list() {
  local token="" query code attempt s3_code hint token_hdr=()
  [ -n "$AWS_SIGV4_TOKEN" ] && token_hdr=(-H "x-amz-security-token: ${AWS_SIGV4_TOKEN}")
  while :; do
    # Parameters in signing order; every value percent-encoded.
    query="list-type=2&prefix=$(uri "$1")"
    [ -n "$token" ] && query="continuation-token=$(uri "$token")&${query}"
    for attempt in 1 2 3; do
      code=$(curl -sS -o "$WORK/list.xml" -w '%{http_code}' --max-time 60 \
        --aws-sigv4 "aws:amz:${REGION}:s3" \
        --user "${AWS_SIGV4_KEY}:${AWS_SIGV4_SECRET}" \
        "${token_hdr[@]}" \
        -H "x-amz-content-sha256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" \
        "${BUCKET_URL}?${query}" 2>/dev/null) || code="000"
      case "$code" in 000|429|5??) sleep $((attempt * 2)); continue ;; esac
      break
    done
    if [ "$code" != "200" ]; then
      s3_code=$(sed -n 's:.*<Code>\(.*\)</Code>.*:\1:p' "$WORK/list.xml" 2>/dev/null | head -1)
      hint=""
      [ "$s3_code" = "AccessDenied" ] && hint=" The daily backup needs s3:ListBucket on the prefix."
      log "ERROR: listing s3://${S3_BUCKET}/$1 failed: HTTP ${code}${s3_code:+ ($s3_code)}.${hint}"
      return 1
    fi
    token=$(python3 - "$WORK/list.xml" "$WORK/present" <<'PY'
import sys, xml.etree.ElementTree as ET
root = ET.parse(sys.argv[1]).getroot()
tag = lambda el: el.tag.split("}")[-1]
with open(sys.argv[2], "a") as out:
    for el in root.iter():
        if tag(el) == "Key" and el.text:
            out.write(el.text.rsplit("/", 1)[-1] + "\n")
truncated = next((el.text for el in root.iter() if tag(el) == "IsTruncated"), "false")
nxt = next((el.text for el in root.iter() if tag(el) == "NextContinuationToken"), "")
print(nxt if truncated == "true" else "")
PY
)
    [ -n "$token" ] || return 0
  done
}

# Every commit folder the window's runs built, filtered out or not, so a run
# the Hub archived under its chain's first commit still counts as present.
: > "$WORK/present"
jq -r '.head_sha' "$WORK/runs.jsonl" | sort -u > "$WORK/shas"
while read -r sha; do
  s3_list "${repo_prefix}/${sha}/" || exit 1
done < "$WORK/shas"

# --- 3. Upload what's missing ---
awk -F'\t' 'FILENAME == ARGV[1] { present[$0] = 1; next } !(($1 "-" $2 ".zip") in present)' \
  "$WORK/present" "$WORK/attempts.tsv" > "$WORK/missing.tsv"
uploaded=0; failed=0
while IFS=$'\t' read -r id attempt sha name; do
  log "backing up ${name} run ${id} attempt ${attempt} (${sha})."
  # Fresh credentials per upload: assumed-role sessions last an hour, and a
  # pass can run longer.
  if s3_credentials "lunar-ci-archive-${id}-${attempt}" < /dev/null &&
    GH_TOKEN="$LUNAR_SECRET_GH_TOKEN" \
    GITHUB_SERVER_URL="https://${HOST}" GITHUB_API_URL="$API_BASE" \
    CI_ARCHIVE_REPOSITORY="$REPO" CI_ARCHIVE_RUN_ID="$id" CI_ARCHIVE_RUN_ATTEMPT="$attempt" \
    CI_ARCHIVE_SHA="$sha" CI_ARCHIVE_UPLOAD=true CI_ARCHIVE_RECORD_IN_LUNAR=false \
    CI_ARCHIVE_S3_BUCKET="$S3_BUCKET" CI_ARCHIVE_S3_PREFIX="$S3_PREFIX" \
    CI_ARCHIVE_S3_ENDPOINT_URL="$S3_ENDPOINT_URL" CI_ARCHIVE_AWS_REGION="$REGION" \
    CI_ARCHIVE_MAX_ARCHIVE_MB="${LUNAR_VAR_MAX_ARCHIVE_MB:-512}" \
    AWS_ACCESS_KEY_ID="$AWS_SIGV4_KEY" AWS_SECRET_ACCESS_KEY="$AWS_SIGV4_SECRET" AWS_SESSION_TOKEN="$AWS_SIGV4_TOKEN" \
    bash "$(dirname "$0")/archive-run.sh" < /dev/null; then
    uploaded=$((uploaded + 1))
  else
    failed=$((failed + 1))
  fi
done < "$WORK/missing.tsv"

if [ "$failed" -gt 0 ]; then
  log "ERROR: ${failed} run attempt(s) on ${WINDOW} could not be backed up (see above); the next pass tries them again."
  exit 1
fi
log "checked ${ATTEMPTS} run attempt(s) on ${WINDOW}: uploaded ${uploaded}, the rest were already in s3://${S3_BUCKET}/${repo_prefix}/."
summary "$uploaded"
