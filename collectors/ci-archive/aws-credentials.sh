#!/bin/bash
# AWS credentials for an S3 upload, sourced by backup-logs-s3.sh and
# backup-logs-s3-daily.sh. The caller defines log() and sets S3_BUCKET and
# S3_ENDPOINT_URL. s3_region sets REGION; s3_credentials sets AWS_SIGV4_KEY /
# _SECRET / _TOKEN and CRED_SOURCE.
#
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

# assume_role_chain <session-name> is the optional aws_assume_role_arns hop, for
# a bucket in another account that only trusts a role there. The first role STS accepts
# replaces the credentials. No DurationSeconds: STS's 1h default is the
# chained-role maximum. ARNs carry an account id, so failures are logged by
# position and STS error code only. AWS_ENDPOINT_URL_STS, the SDKs' override,
# points it at another STS endpoint.
assume_role_chain() {
  local raw=() arns=() arn resp status parsed reason session sts i=0
  local token_hdr=() external_id=()
  # Commas or whitespace separate entries; an ARN never contains whitespace.
  local role_arns="${LUNAR_VAR_AWS_ASSUME_ROLE_ARNS:-}" ext="${LUNAR_VAR_AWS_EXTERNAL_ID:-}"
  IFS=',' read -ra raw <<< "${role_arns//[[:space:]]/,}"
  for arn in "${raw[@]}"; do
    if [ -n "$arn" ]; then arns+=("$arn"); fi
  done
  if [ "${#arns[@]}" -eq 0 ]; then return 0; fi

  sts="${AWS_ENDPOINT_URL_STS:-https://sts.${REGION}.amazonaws.com}"
  session="$(printf '%s' "$1" | tr -c 'A-Za-z0-9+=,.@_-' '_' | cut -c1-64)"
  if [ -n "$AWS_SIGV4_TOKEN" ]; then
    token_hdr=(-H "x-amz-security-token: ${AWS_SIGV4_TOKEN}")
  fi
  if [ -n "$ext" ]; then
    external_id=(--data-urlencode "ExternalId=${ext}")
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

# s3_region sets REGION for S3_BUCKET: the aws_region input, then the
# environment, then the region S3 reports for the bucket.
s3_region() {
  REGION="${LUNAR_VAR_AWS_REGION:-${AWS_REGION:-${AWS_DEFAULT_REGION:-}}}"
  if [ -n "$S3_ENDPOINT_URL" ]; then
    REGION="${REGION:-us-east-1}"
    return 0
  fi
  if [ -z "$REGION" ]; then
    # S3 reports a bucket's region on any HEAD, even an unauthenticated 403.
    REGION="$(curl -sSI --max-time 10 "https://s3.amazonaws.com/${S3_BUCKET}" 2>/dev/null \
      | tr -d '\r' | awk -F': ' 'tolower($1) == "x-amz-bucket-region" { print $2; exit }')" || true
  fi
  if [ -z "$REGION" ]; then
    log "ERROR: could not determine the region of bucket ${S3_BUCKET}; set the aws_region input."
    return 1
  fi
}

# s3_credentials <session-name> resolves the base credentials, then takes the
# aws_assume_role_arns hop under that STS session name.
s3_credentials() {
  if [ -n "$S3_ENDPOINT_URL" ]; then
    # S3-compatible store: AWS roles mean nothing there, only static keys do.
    if ! use_static_keys; then
      log "ERROR: s3_endpoint_url is set but the AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY secrets are not."
      return 1
    fi
  else
    resolve_aws_credentials || return 1
  fi
  assume_role_chain "$1"
}
