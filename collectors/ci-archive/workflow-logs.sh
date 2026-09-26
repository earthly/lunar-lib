#!/bin/bash
set -eo pipefail

# Archive the CI workflow run attempt this collector fired for -- run metadata,
# jobs and the full log archive -- to S3, and record it as one entry under
# .ci.archive.runs.
#
# Runs on the workflow-end hook: once per finished run attempt, re-runs
# included, with the run in LUNAR_CI_PIPELINE_*. The archiving is archive-run.sh,
# shared with the GitHub Action; this wrapper supplies what the Hub knows in
# place of a CI job: the repository, from the component, and AWS credentials,
# from the pod's IAM role or the collector secrets, optionally exchanged for a
# role in the bucket's account.

log() { echo "ci-archive: $*" >&2; }

S3_BUCKET="${LUNAR_VAR_S3_BUCKET:-}"
S3_ENDPOINT_URL="${LUNAR_VAR_S3_ENDPOINT_URL:-}"
ASSUME_ROLE_ARNS="${LUNAR_VAR_AWS_ASSUME_ROLE_ARNS:-}"
EXTERNAL_ID="${LUNAR_VAR_AWS_EXTERNAL_ID:-}"
INCLUDE_RUNS_PATTERN="${LUNAR_VAR_INCLUDE_RUNS_PATTERN:-}"
RUN_ID="${LUNAR_CI_PIPELINE_RUN_ID:-}"
ATTEMPT="${LUNAR_CI_PIPELINE_RUN_ATTEMPT:-}"
WORKFLOW="${LUNAR_CI_PIPELINE_NAME:-}"

if [ -z "${LUNAR_SECRET_GH_TOKEN:-}" ]; then
  log "GH_TOKEN secret is not set; skipping."
  exit 0
fi
if [ -z "$RUN_ID" ] || [ -z "$ATTEMPT" ] || [ -z "${LUNAR_COMPONENT_ID:-}" ]; then
  log "no workflow run in context: this collector runs on the Hub's workflow-end hook. Skipping."
  exit 0
fi
if [ -n "$INCLUDE_RUNS_PATTERN" ]; then
  if ! jq -n --arg re "$INCLUDE_RUNS_PATTERN" '"" | test($re)' >/dev/null 2>&1; then
    log "ERROR: include_runs_pattern is not a valid regex: ${INCLUDE_RUNS_PATTERN}"
    exit 1
  fi
  if ! jq -en --arg re "$INCLUDE_RUNS_PATTERN" --arg name "$WORKFLOW" '$name | test($re)' >/dev/null; then
    log "workflow '${WORKFLOW}' does not match include_runs_pattern; skipping run ${RUN_ID}."
    exit 0
  fi
fi

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

# --- AWS credentials ---
# The helpers mirror collectors/backstage/main.sh: role-based sources first,
# the shared-pool LUNAR_SECRET_AWS_* keys last.

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

# assume_role_chain is the optional aws_assume_role_arns hop, for a bucket in
# another account that only trusts a role there. The first role STS accepts
# replaces the credentials. No DurationSeconds: STS's 1h default is the
# chained-role maximum. ARNs carry an account id, so failures are logged by
# position and STS error code only. AWS_ENDPOINT_URL_STS, the SDKs' override,
# points it at another STS endpoint.
assume_role_chain() {
  local raw=() arns=() arn resp status parsed reason session sts i=0
  local token_hdr=() external_id=()
  # Commas or whitespace separate entries; an ARN never contains whitespace.
  IFS=',' read -ra raw <<< "${ASSUME_ROLE_ARNS//[[:space:]]/,}"
  for arn in "${raw[@]}"; do
    if [ -n "$arn" ]; then arns+=("$arn"); fi
  done
  if [ "${#arns[@]}" -eq 0 ]; then return 0; fi

  sts="${AWS_ENDPOINT_URL_STS:-https://sts.${REGION}.amazonaws.com}"
  # Named per run attempt, so the bucket account's CloudTrail says which run
  # each upload belongs to.
  session="$(printf 'lunar-ci-archive-%s-%s' "$RUN_ID" "$ATTEMPT" | tr -c 'A-Za-z0-9+=,.@_-' '_' | cut -c1-64)"
  if [ -n "$AWS_SIGV4_TOKEN" ]; then
    token_hdr=(-H "x-amz-security-token: ${AWS_SIGV4_TOKEN}")
  fi
  if [ -n "$EXTERNAL_ID" ]; then
    external_id=(--data-urlencode "ExternalId=${EXTERNAL_ID}")
  fi
  for arn in "${arns[@]}"; do
    i=$((i + 1))
    status=0
    resp="$(curl -sS --max-time 15 --get "${sts%/}/" \
      --aws-sigv4 "aws:amz:${REGION}:sts" \
      --user "${AWS_SIGV4_KEY}:${AWS_SIGV4_SECRET}" \
      "${token_hdr[@]}" \
      --data-urlencode "Action=AssumeRole" \
      --data-urlencode "Version=2011-06-15" \
      --data-urlencode "RoleArn=${arn}" \
      --data-urlencode "RoleSessionName=${session}" \
      "${external_id[@]}" 2>/dev/null)" || status=$?
    if [ "$status" -eq 0 ] && parsed="$(printf '%s' "$resp" | parse_sts_credentials)"; then
      AWS_SIGV4_KEY="$(printf '%s\n' "$parsed" | sed -n 1p)"
      AWS_SIGV4_SECRET="$(printf '%s\n' "$parsed" | sed -n 2p)"
      AWS_SIGV4_TOKEN="$(printf '%s\n' "$parsed" | sed -n 3p)"
      CRED_SOURCE="${CRED_SOURCE}+assume-role"
      return 0
    fi
    if [ "$status" -ne 0 ]; then
      reason="request failed, curl exit ${status}"
    elif [[ "$resp" == *"<Code>"*"</Code>"* ]]; then
      reason="${resp#*<Code>}"; reason="${reason%%</Code>*}"
    else
      reason="unrecognized STS response"
    fi
    log "aws_assume_role_arns role ${i}/${#arns[@]} not assumed (${reason})."
  done
  log "ERROR: sts:AssumeRole failed for every role in aws_assume_role_arns. The base identity"
  log "  (${CRED_SOURCE}) needs sts:AssumeRole on the role, and the role's trust policy must"
  log "  allow it, with aws_external_id if the policy requires one."
  return 1
}

REGION="${LUNAR_VAR_AWS_REGION:-${AWS_REGION:-${AWS_DEFAULT_REGION:-}}}"
UPLOAD=true
if [ -z "$S3_BUCKET" ]; then
  UPLOAD=false
  log "s3_bucket is not set: recording run ${RUN_ID} attempt ${ATTEMPT} without uploading it."
elif [ -n "$S3_ENDPOINT_URL" ]; then
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
if [ "$UPLOAD" = true ]; then
  assume_role_chain || exit 1
  log "uploading to bucket ${S3_BUCKET} (${REGION}) with AWS credentials from ${CRED_SOURCE}."
fi

GH_TOKEN="$LUNAR_SECRET_GH_TOKEN" \
GITHUB_SERVER_URL="https://${HOST}" GITHUB_API_URL="$API_BASE" \
CI_ARCHIVE_REPOSITORY="$REPO" CI_ARCHIVE_RUN_ID="$RUN_ID" CI_ARCHIVE_RUN_ATTEMPT="$ATTEMPT" \
CI_ARCHIVE_UPLOAD="$UPLOAD" CI_ARCHIVE_SHA="${LUNAR_COMPONENT_GIT_SHA:-}" CI_ARCHIVE_TRIGGERED_BY_RUN_ID="${LUNAR_CI_PIPELINE_TRIGGERED_BY_RUN_ID:-}" \
CI_ARCHIVE_ORIGIN_SOURCE="${LUNAR_CI_PIPELINE_ORIGIN_SOURCE:-}" \
CI_ARCHIVE_S3_BUCKET="$S3_BUCKET" CI_ARCHIVE_S3_PREFIX="${LUNAR_VAR_S3_PREFIX-lunar/ci-archive}" \
CI_ARCHIVE_S3_ENDPOINT_URL="$S3_ENDPOINT_URL" CI_ARCHIVE_AWS_REGION="$REGION" \
CI_ARCHIVE_MAX_ARCHIVE_MB="${LUNAR_VAR_MAX_ARCHIVE_MB:-512}" CI_ARCHIVE_INTEGRATION=workflow-end \
CI_ARCHIVE_INCLUDE_EVENTS="${LUNAR_VAR_INCLUDE_EVENTS:-}" \
AWS_ACCESS_KEY_ID="$AWS_SIGV4_KEY" AWS_SECRET_ACCESS_KEY="$AWS_SIGV4_SECRET" AWS_SESSION_TOKEN="$AWS_SIGV4_TOKEN" \
  exec bash "$(dirname "$0")/archive-run.sh"
