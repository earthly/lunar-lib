#!/bin/bash
set -eo pipefail

# Archive every completed CI workflow run for this commit — run metadata plus
# the provider's log archive — into one zip in S3, and record where it went
# under .ci.archive.
#
# Runs at the doneness gate (after-json + missing-json on .ci), so every run
# relevant to the commit has already finished. There is no source tree and no
# CI env here: runs are resolved from the commit via the GitHub Actions API.

log() { echo "ci-archive: $*" >&2; }

# --- Inputs (in-script fallbacks mirror the manifest defaults) ---
S3_BUCKET="${LUNAR_VAR_S3_BUCKET:-}"
# No colon: an explicit empty prefix means "bucket root".
S3_PREFIX="${LUNAR_VAR_S3_PREFIX-lunar/ci-archive}"
S3_ENDPOINT_URL="${LUNAR_VAR_S3_ENDPOINT_URL:-}"
MAX_ARCHIVE_MB="${LUNAR_VAR_MAX_ARCHIVE_MB:-512}"
INCLUDE_RUNS_PATTERN="${LUNAR_VAR_INCLUDE_RUNS_PATTERN:-}"
SHA="${LUNAR_COMPONENT_GIT_SHA:-}"

if [ -z "$S3_BUCKET" ]; then
  log "s3_bucket input is not set; skipping."
  exit 0
fi
if [ -z "${LUNAR_SECRET_GH_TOKEN:-}" ]; then
  log "GH_TOKEN secret is not set; skipping."
  exit 0
fi
if [ -z "$SHA" ] || [ -z "${LUNAR_COMPONENT_ID:-}" ]; then
  log "no component or commit in context; skipping."
  exit 0
fi
if ! [[ "$MAX_ARCHIVE_MB" =~ ^[0-9]+$ ]] || [ "$MAX_ARCHIVE_MB" -eq 0 ]; then
  log "ERROR: max_archive_mb must be a positive integer, got '${MAX_ARCHIVE_MB}'."
  exit 1
fi
if [ -n "$INCLUDE_RUNS_PATTERN" ] && ! jq -n --arg re "$INCLUDE_RUNS_PATTERN" '"" | test($re)' >/dev/null 2>&1; then
  log "ERROR: include_runs_pattern is not a valid regex: ${INCLUDE_RUNS_PATTERN}"
  exit 1
fi
MAX_BYTES=$((MAX_ARCHIVE_MB * 1024 * 1024))

# Component IDs are <host>/<owner>/<repository>[/<subpath>...]; monorepo
# components append a path after the repository.
HOST="${LUNAR_COMPONENT_ID%%/*}"
REST="${LUNAR_COMPONENT_ID#*/}"
OWNER="${REST%%/*}"
REST="${REST#*/}"
REPO="${OWNER}/${REST%%/*}"
case "$HOST" in
  *gitlab*) log "GitHub Actions only; ${HOST} is not supported. Skipping."; exit 0 ;;
esac
API_BASE="https://api.github.com"
if [ "$HOST" != "github.com" ]; then
  API_BASE="https://${HOST}/api/v3"
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# gh_get <url> <outfile> prints the HTTP status. Retries connection failures,
# 429 and 5xx; everything else is the caller's to interpret.
gh_get() {
  local url="$1" out="$2" code attempt=0
  while :; do
    attempt=$((attempt + 1))
    code=$(curl -sS -o "$out" -w '%{http_code}' --max-time 60 \
      -H "Accept: application/vnd.github+json" \
      -H "Authorization: Bearer ${LUNAR_SECRET_GH_TOKEN}" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      "$url" 2>/dev/null) || code="000"
    case "$code" in
      000|429|5??)
        if [ "$attempt" -lt 3 ]; then sleep $((attempt * 2)); continue; fi ;;
    esac
    printf '%s' "$code"
    return 0
  done
}

# --- 1. Resolve the workflow runs at this commit ---
RUNS="$WORK/runs.json"
echo '[]' > "$RUNS"
page=1
while [ "$page" -le 10 ]; do
  code=$(gh_get "${API_BASE}/repos/${REPO}/actions/runs?head_sha=${SHA}&per_page=100&page=${page}&exclude_pull_requests=true" "$WORK/page.json")
  if [ "$code" != "200" ]; then
    log "ERROR: listing workflow runs for ${REPO}@${SHA} returned HTTP ${code}."
    case "$code" in
      401) log "  GH_TOKEN was rejected." ;;
      403|404) log "  GH_TOKEN needs actions:read on ${REPO}." ;;
    esac
    exit 1
  fi
  count=$(jq '.workflow_runs | length' "$WORK/page.json")
  jq -s '.[0] + .[1].workflow_runs' "$RUNS" "$WORK/page.json" > "$WORK/merged.json"
  mv "$WORK/merged.json" "$RUNS"
  total=$(jq '.total_count' "$WORK/page.json")
  if [ "$count" -lt 100 ] || [ "$(jq 'length' "$RUNS")" -ge "$total" ]; then
    break
  fi
  page=$((page + 1))
done

# GitHub has no completed_at on a run; updated_at is when it finished.
jq --arg re "$INCLUDE_RUNS_PATTERN" '
  map(select($re == "" or ((.name // "") | test($re))))
  | map({
      id, name, path, event,
      attempt: .run_attempt,
      status, conclusion,
      started_at: .run_started_at,
      completed_at: (if .status == "completed" then .updated_at else null end),
      html_url
    })' "$RUNS" > "$WORK/candidates.json"

jq '[.[] | select(.status == "completed")]' "$WORK/candidates.json" > "$WORK/completed.json"
ERRORS="$WORK/errors.json"
jq '[.[] | select(.status != "completed")
      | {run_id: .id, name, reason: ("not completed at archive time (" + .status + ")")}]' \
  "$WORK/candidates.json" > "$ERRORS"

COMPLETED_COUNT=$(jq 'length' "$WORK/completed.json")
if [ "$COMPLETED_COUNT" -eq 0 ]; then
  log "no completed workflow runs for ${REPO}@${SHA}; nothing to archive."
  jq -r '.[] | "  skipped run \(.run_id) (\(.name)): \(.reason)"' "$ERRORS" >&2
  exit 0
fi
log "${COMPLETED_COUNT} completed workflow run(s) for ${REPO}@${SHA}."

# --- 2. Resolve the S3 target and AWS credentials (before downloading) ---
# The credential helpers mirror collectors/backstage/main.sh: role-based
# sources first, the shared-pool LUNAR_SECRET_AWS_* keys last.

# parse_sts_credentials reads an STS query-protocol (XML) response on stdin and
# prints AccessKeyId, SecretAccessKey and SessionToken, one per line.
parse_sts_credentials() {
  python3 -c '
import sys, xml.etree.ElementTree as ET
try:
    root = ET.fromstring(sys.stdin.read())
except Exception:
    sys.exit(1)
def find(tag):
    for el in root.iter():
        if el.tag.split("}")[-1] == tag:
            return el.text or ""
    return ""
kid, sec, tok = find("AccessKeyId"), find("SecretAccessKey"), find("SessionToken")
if not (kid and sec):
    sys.exit(1)
print(kid); print(sec); print(tok)
' 2>/dev/null
}

use_static_keys() {
  if [ -n "${LUNAR_SECRET_AWS_ACCESS_KEY_ID:-}" ] && [ -n "${LUNAR_SECRET_AWS_SECRET_ACCESS_KEY:-}" ]; then
    AWS_SIGV4_KEY="${LUNAR_SECRET_AWS_ACCESS_KEY_ID}"
    AWS_SIGV4_SECRET="${LUNAR_SECRET_AWS_SECRET_ACCESS_KEY}"
    AWS_SIGV4_TOKEN="${LUNAR_SECRET_AWS_SESSION_TOKEN:-}"
    CRED_SOURCE="static-keys"
    return 0
  fi
  return 1
}

# Order: IRSA / EKS Pod Identity -> ECS task role -> EC2 IMDSv2 -> static.
resolve_aws_credentials() {
  AWS_SIGV4_KEY=""; AWS_SIGV4_SECRET=""; AWS_SIGV4_TOKEN=""; CRED_SOURCE=""

  if [ -n "${AWS_WEB_IDENTITY_TOKEN_FILE:-}" ] && [ -n "${AWS_ROLE_ARN:-}" ] \
     && [ -f "${AWS_WEB_IDENTITY_TOKEN_FILE}" ]; then
    local wit resp parsed
    wit="$(cat "$AWS_WEB_IDENTITY_TOKEN_FILE")"
    resp="$(curl -sS -X POST "https://sts.${REGION}.amazonaws.com/" \
      --data-urlencode "Action=AssumeRoleWithWebIdentity" \
      --data-urlencode "Version=2011-06-15" \
      --data-urlencode "RoleArn=${AWS_ROLE_ARN}" \
      --data-urlencode "RoleSessionName=${AWS_ROLE_SESSION_NAME:-lunar-ci-archive-collector}" \
      --data-urlencode "DurationSeconds=3600" \
      --data-urlencode "WebIdentityToken=${wit}" 2>/dev/null)" || true
    parsed="$(printf '%s' "$resp" | parse_sts_credentials)" || true
    if [ -n "$parsed" ]; then
      AWS_SIGV4_KEY="$(printf '%s\n' "$parsed" | sed -n 1p)"
      AWS_SIGV4_SECRET="$(printf '%s\n' "$parsed" | sed -n 2p)"
      AWS_SIGV4_TOKEN="$(printf '%s\n' "$parsed" | sed -n 3p)"
      CRED_SOURCE="irsa-web-identity"; return 0
    fi
    log "ERROR: web-identity (IRSA) credential resolution failed. STS response head:"
    printf '%s' "$resp" | head -c 300 >&2; echo "" >&2
    return 1
  fi

  if [ -n "${AWS_CONTAINER_CREDENTIALS_FULL_URI:-}" ] || [ -n "${AWS_CONTAINER_CREDENTIALS_RELATIVE_URI:-}" ]; then
    local ecs_url auth_val=""; local hdr=()
    if [ -n "${AWS_CONTAINER_CREDENTIALS_FULL_URI:-}" ]; then
      ecs_url="$AWS_CONTAINER_CREDENTIALS_FULL_URI"
    else
      ecs_url="http://169.254.170.2${AWS_CONTAINER_CREDENTIALS_RELATIVE_URI}"
    fi
    if [ -n "${AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE:-}" ] && [ -f "${AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE}" ]; then
      auth_val="$(cat "${AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE}")"
    elif [ -n "${AWS_CONTAINER_AUTHORIZATION_TOKEN:-}" ]; then
      auth_val="${AWS_CONTAINER_AUTHORIZATION_TOKEN}"
    fi
    [ -n "$auth_val" ] && hdr=(-H "Authorization: $auth_val")
    resp="$(curl -sS --connect-timeout 3 --max-time 5 "${hdr[@]}" "$ecs_url" 2>/dev/null)" || true
    AWS_SIGV4_KEY="$(printf '%s' "$resp" | jq -r '.AccessKeyId // empty' 2>/dev/null)"
    AWS_SIGV4_SECRET="$(printf '%s' "$resp" | jq -r '.SecretAccessKey // empty' 2>/dev/null)"
    AWS_SIGV4_TOKEN="$(printf '%s' "$resp" | jq -r '.Token // empty' 2>/dev/null)"
    if [ -n "$AWS_SIGV4_KEY" ] && [ -n "$AWS_SIGV4_SECRET" ]; then
      CRED_SOURCE="container-credentials"; return 0
    fi
    log "ERROR: container-credentials (ECS / EKS Pod Identity) resolution failed."
    return 1
  fi

  local imds_token role
  imds_token="$(curl -sS -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 300" --connect-timeout 2 --max-time 5 2>/dev/null)" || true
  if [ -n "$imds_token" ]; then
    role="$(curl -sSf --connect-timeout 2 --max-time 5 -H "X-aws-ec2-metadata-token: $imds_token" \
      "http://169.254.169.254/latest/meta-data/iam/security-credentials/" 2>/dev/null)" || true
    if [ -n "$role" ]; then
      resp="$(curl -sSf --connect-timeout 2 --max-time 5 -H "X-aws-ec2-metadata-token: $imds_token" \
        "http://169.254.169.254/latest/meta-data/iam/security-credentials/${role}" 2>/dev/null)" || true
      AWS_SIGV4_KEY="$(printf '%s' "$resp" | jq -r '.AccessKeyId // empty' 2>/dev/null)"
      AWS_SIGV4_SECRET="$(printf '%s' "$resp" | jq -r '.SecretAccessKey // empty' 2>/dev/null)"
      AWS_SIGV4_TOKEN="$(printf '%s' "$resp" | jq -r '.Token // empty' 2>/dev/null)"
      if [ -n "$AWS_SIGV4_KEY" ] && [ -n "$AWS_SIGV4_SECRET" ]; then
        CRED_SOURCE="ec2-instance-profile"; return 0
      fi
    fi
  fi

  use_static_keys && return 0

  log "ERROR: no AWS credentials could be resolved. Tried (in order): IRSA / EKS Pod"
  log "  Identity web-identity, ECS / Pod Identity container credentials, EC2 IMDSv2,"
  log "  then the AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY secrets."
  return 1
}

REGION="${LUNAR_VAR_AWS_REGION:-${AWS_REGION:-${AWS_DEFAULT_REGION:-}}}"
if [ -n "$S3_ENDPOINT_URL" ]; then
  # S3-compatible store: AWS roles mean nothing there, only static keys do.
  REGION="${REGION:-us-east-1}"
  if ! use_static_keys; then
    log "ERROR: s3_endpoint_url is set but the AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY secrets are not."
    exit 1
  fi
else
  if [ -z "$REGION" ]; then
    # S3 reports a bucket's region on any HEAD, even an unauthenticated 403.
    REGION="$(curl -sSI --max-time 10 "https://s3.amazonaws.com/${S3_BUCKET}" 2>/dev/null \
      | tr -d '\r' | awk -F': ' 'tolower($1) == "x-amz-bucket-region" { print $2; exit }')" || true
  fi
  if [ -z "$REGION" ]; then
    log "ERROR: could not determine the region of bucket ${S3_BUCKET}; set the aws_region input."
    exit 1
  fi
  resolve_aws_credentials || exit 1
fi
log "uploading to bucket ${S3_BUCKET} (${REGION}) with AWS credentials from ${CRED_SOURCE}."

# --- 3. Download each run's logs into the archive ---
# Each provider zip is added as soon as it lands and then deleted, so staging
# never holds more than the archive plus one run's logs.
ARCHIVE="$WORK/archive.zip"
zip_add() {
  python3 - "$@" <<'PY'
import sys, zipfile
archive, arcname, path, mode = sys.argv[1:5]
comp = zipfile.ZIP_STORED if mode == "stored" else zipfile.ZIP_DEFLATED
with zipfile.ZipFile(archive, "a", compression=comp, allowZip64=True) as zf:
    zf.write(path, arcname, compress_type=comp)
PY
}
add_error() {
  jq --argjson id "${1:-null}" --arg name "${2:-}" --arg reason "$3" \
    '. + [{run_id: $id, name: (if $name == "" then null else $name end), reason: $reason}
          | with_entries(select(.value != null))]' \
    "$ERRORS" > "$WORK/errors.tmp" && mv "$WORK/errors.tmp" "$ERRORS"
}
file_size() { wc -c < "$1" | tr -d ' '; }

ARCHIVED="$WORK/archived.json"
echo '[]' > "$ARCHIVED"
OVER_CAP=false
index=0
while IFS= read -r run; do
  index=$((index + 1))
  id=$(jq -r '.id' <<< "$run")
  name=$(jq -r '.name // ""' <<< "$run")

  # The logs endpoint 302s to a short-lived signed URL; fetch that without the
  # token, which must not leave for another host.
  code=""; loc=""
  for attempt in 1 2 3; do
    out=$(curl -sS -o /dev/null -w '%{http_code} %{redirect_url}' --max-time 60 \
      -H "Accept: application/vnd.github+json" \
      -H "Authorization: Bearer ${LUNAR_SECRET_GH_TOKEN}" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      "${API_BASE}/repos/${REPO}/actions/runs/${id}/logs" 2>/dev/null) || out="000 "
    code="${out%% *}"; loc="${out#* }"
    case "$code" in 000|429|5??) sleep $((attempt * 2)); continue ;; esac
    break
  done
  case "$code" in
    302) ;;
    410) add_error "$id" "$name" "logs expired or deleted (410)"; continue ;;
    404) add_error "$id" "$name" "logs not found (404)"; continue ;;
    *)   add_error "$id" "$name" "log download returned HTTP ${code}"; continue ;;
  esac

  used=0
  [ -f "$ARCHIVE" ] && used=$(file_size "$ARCHIVE")
  status=0
  if [ $((MAX_BYTES - used)) -le 0 ]; then
    status=63
  else
    curl -sS -f -o "$WORK/logs.zip" --max-time 900 --retry 2 \
      --max-filesize $((MAX_BYTES - used)) "$loc" 2>/dev/null || status=$?
  fi
  if [ "$status" -eq 63 ]; then
    OVER_CAP=true
  elif [ "$status" -ne 0 ]; then
    add_error "$id" "$name" "log archive download failed (curl exit ${status})"
    rm -f "$WORK/logs.zip"; continue
  elif ! python3 -c 'import sys, zipfile; sys.exit(0 if zipfile.is_zipfile(sys.argv[1]) else 1)' "$WORK/logs.zip"; then
    add_error "$id" "$name" "log archive is not a valid zip"
    rm -f "$WORK/logs.zip"; continue
  else
    log_bytes=$(file_size "$WORK/logs.zip")
    zip_add "$ARCHIVE" "runs/${id}/logs.zip" "$WORK/logs.zip" stored
    rm -f "$WORK/logs.zip"
    jq --argjson run "$run" --argjson bytes "$log_bytes" '. + [$run + {log_bytes: $bytes}]' \
      "$ARCHIVED" > "$WORK/archived.tmp" && mv "$WORK/archived.tmp" "$ARCHIVED"
    [ "$(file_size "$ARCHIVE")" -gt "$MAX_BYTES" ] && OVER_CAP=true
  fi
  if [ "$OVER_CAP" = true ]; then
    add_error "" "" "archive exceeded max_archive_mb (${MAX_ARCHIVE_MB} MB) at run ${index} of ${COMPLETED_COUNT}; not uploaded"
    rm -f "$WORK/logs.zip"
    break
  fi
done < <(jq -c '.[]' "$WORK/completed.json")

ARCHIVED_COUNT=$(jq 'length' "$ARCHIVED")
COLLECTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
SOURCE_JSON=$(jq -n --arg at "$COLLECTED_AT" --arg sha "$SHA" \
  '{tool: "ci-archive", integration: "after-json", collected_at: $at, collected_sha: $sha}')

# Nothing to upload: every run failed, or the cap was hit. Record why.
if [ "$OVER_CAP" = true ] || [ "$ARCHIVED_COUNT" -eq 0 ]; then
  log "nothing uploaded; see .ci.archive.errors."
  jq -n --argjson source "$SOURCE_JSON" --slurpfile errors "$ERRORS" \
    '{errors: $errors[0], source: $source}' | lunar collect -j ".ci.archive" -
  exit 0
fi

# --- 4. Add the manifest and upload ---
jq -n --arg component "$LUNAR_COMPONENT_ID" --arg repo "$REPO" --arg sha "$SHA" \
  --arg pr "${LUNAR_COMPONENT_PR:-}" --arg at "$COLLECTED_AT" \
  --slurpfile runs "$ARCHIVED" --slurpfile errors "$ERRORS" '{
    component: $component, repository: $repo, sha: $sha,
    pr: (if $pr == "" then null else ($pr | tonumber? // $pr) end),
    archived_at: $at, runs: $runs[0], errors: $errors[0]
  }' > "$WORK/manifest.json"
zip_add "$ARCHIVE" "manifest.json" "$WORK/manifest.json" deflated

# Key characters outside this set would need encoding in both the URL and
# the SigV4 canonical path; component IDs never use them in practice.
prefix="${S3_PREFIX#/}"; prefix="${prefix%/}"
KEY="${LUNAR_COMPONENT_ID}/${SHA}/$(date -u +%Y%m%dT%H%M%SZ).zip"
[ -n "$prefix" ] && KEY="${prefix}/${KEY}"
KEY="$(printf '%s' "$KEY" | tr -c 'A-Za-z0-9._/-' '_')"

if [ -n "$S3_ENDPOINT_URL" ]; then
  URL="${S3_ENDPOINT_URL%/}/${S3_BUCKET}/${KEY}"
elif [[ "$S3_BUCKET" == *.* ]]; then
  # Dotted bucket names break the virtual-host TLS wildcard.
  URL="https://s3.${REGION}.amazonaws.com/${S3_BUCKET}/${KEY}"
else
  URL="https://${S3_BUCKET}.s3.${REGION}.amazonaws.com/${KEY}"
fi

SIZE=$(file_size "$ARCHIVE")
PAYLOAD_SHA=$(sha256sum "$ARCHIVE" | cut -d' ' -f1)
token_hdr=()
[ -n "$AWS_SIGV4_TOKEN" ] && token_hdr=(-H "x-amz-security-token: ${AWS_SIGV4_TOKEN}")
code=""
for attempt in 1 2 3; do
  code=$(curl -sS -o "$WORK/s3.out" -w '%{http_code}' --max-time 1800 -X PUT \
    --aws-sigv4 "aws:amz:${REGION}:s3" \
    --user "${AWS_SIGV4_KEY}:${AWS_SIGV4_SECRET}" \
    "${token_hdr[@]}" \
    -H "x-amz-content-sha256: ${PAYLOAD_SHA}" \
    -H "Content-Type: application/zip" \
    -T "$ARCHIVE" "$URL" 2>/dev/null) || code="000"
  case "$code" in 000|429|5??) sleep $((attempt * 2)); continue ;; esac
  break
done
if [ "$code" != "200" ]; then
  s3_code=$(sed -n 's:.*<Code>\(.*\)</Code>.*:\1:p' "$WORK/s3.out" 2>/dev/null | head -1)
  log "ERROR: S3 upload to s3://${S3_BUCKET}/${KEY} failed: HTTP ${code}${s3_code:+ ($s3_code)}."
  exit 1
fi
log "uploaded s3://${S3_BUCKET}/${KEY} (${SIZE} bytes, ${ARCHIVED_COUNT} run(s))."

# --- 5. Record the receipt ---
jq -n --arg bucket "$S3_BUCKET" --arg key "$KEY" --argjson size "$SIZE" \
  --argjson source "$SOURCE_JSON" --slurpfile runs "$ARCHIVED" --slurpfile errors "$ERRORS" '
  {uri: ("s3://" + $bucket + "/" + $key), bucket: $bucket, key: $key, size_bytes: $size,
   run_count: ($runs[0] | length), runs: $runs[0]}
  + (if ($errors[0] | length) > 0 then {errors: $errors[0]} else {} end)
  + {source: $source}' | lunar collect -j ".ci.archive" -
