#!/bin/bash
# shellcheck disable=SC2034  # LIVE_* and SEARCHED are read by oncall.sh
# Live Backstage lookup for backstage_discovery, sourced by oncall.sh.
#
# Finds the repo's Component in the live catalog and reads the service ID off
# it, else off its System, else off that System's Domain — so an ID declared
# once on a System or Domain reaches every Component under it. Auth, endpoints
# and reference parsing mirror collectors/backstage/main.sh.
#
# The AWS helpers below (parse_sts_credentials, resolve_aws_credentials,
# assume_role_chain) and url_escape are copies of the ones in
# collectors/backstage/main.sh and catalogers/backstage/main.sh: all three run in
# the same snippet pods, so credentials must resolve identically.
# scripts/validate_shared_helpers.py fails +lint when the copies drift.

# Inputs. `-` not `:-` on the prefix: an explicit "" must survive, to mount the
# catalog API at the root (see collectors/backstage/main.sh).
BACKSTAGE_BASE_URL="${LUNAR_VAR_BACKSTAGE_URL:-}"
BACKSTAGE_BASE_URL="${BACKSTAGE_BASE_URL%/}"
BACKSTAGE_API_PATH_PREFIX="${LUNAR_VAR_BACKSTAGE_API_PATH_PREFIX-/api}"
BACKSTAGE_API_PATH_PREFIX="${BACKSTAGE_API_PATH_PREFIX%/}"
if [ -n "$BACKSTAGE_API_PATH_PREFIX" ] && [ "${BACKSTAGE_API_PATH_PREFIX#/}" = "$BACKSTAGE_API_PATH_PREFIX" ]; then
  BACKSTAGE_API_PATH_PREFIX="/$BACKSTAGE_API_PATH_PREFIX"
fi
AUTH_MODE="${LUNAR_VAR_BACKSTAGE_AUTH_MODE:-bearer}"
REF_LOOKUP="${LUNAR_VAR_BACKSTAGE_REF_LOOKUP:-by-name}"
ANNOTATION_KEYS="${LUNAR_VAR_BACKSTAGE_ANNOTATIONS:-pagerduty.com/service-id,pagerduty/service-id}"

# parse_sts_credentials reads an STS query-protocol (XML) response on stdin and
# prints AccessKeyId, SecretAccessKey and SessionToken, one per line. Exits 1
# when the response carries no credentials (an <ErrorResponse>, or not XML).
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

# resolve_aws_credentials walks the AWS credential provider chain and sets
# AWS_SIGV4_KEY / AWS_SIGV4_SECRET / AWS_SIGV4_TOKEN / CRED_SOURCE.
#
# Role-based sources are tried FIRST so an attached role always wins and stays
# self-refreshing; explicit static keys (LUNAR_SECRET_AWS_*) are the last-resort
# escape hatch for runners with no IAM identity. We deliberately do NOT read the
# ambient AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY env — a stray env var (from a
# sidecar, a Secret mount, dev tooling) must not silently preempt an annotated
# role, which would break the self-refresh guarantee the docs promise. This
# matches the README's numbering (IRSA #1 recommended ... static #4 escape hatch).
# Order: IRSA / EKS Pod Identity -> ECS task role -> EC2 IMDSv2 -> static secret.
# Uses only curl + jq + python3 (all in base-main); no aws CLI / botocore.
resolve_aws_credentials() {
  AWS_SIGV4_KEY=""; AWS_SIGV4_SECRET=""; AWS_SIGV4_TOKEN=""; CRED_SOURCE=""

  # 1. IRSA / web identity: exchange the projected token for temp creds via
  #    STS AssumeRoleWithWebIdentity (token-authenticated POST, no signing).
  if [ -n "${AWS_WEB_IDENTITY_TOKEN_FILE:-}" ] && [ -n "${AWS_ROLE_ARN:-}" ] \
     && [ -f "${AWS_WEB_IDENTITY_TOKEN_FILE}" ]; then
    local wit resp parsed
    wit="$(cat "$AWS_WEB_IDENTITY_TOKEN_FILE")"
    resp="$(curl -sS -X POST "https://sts.${AWS_SIGV4_REGION}.amazonaws.com/" \
      --data-urlencode "Action=AssumeRoleWithWebIdentity" \
      --data-urlencode "Version=2011-06-15" \
      --data-urlencode "RoleArn=${AWS_ROLE_ARN}" \
      --data-urlencode "RoleSessionName=${AWS_ROLE_SESSION_NAME:-lunar-pagerduty-collector}" \
      --data-urlencode "DurationSeconds=3600" \
      --data-urlencode "WebIdentityToken=${wit}" 2>/dev/null)" || true
    parsed="$(printf '%s' "$resp" | parse_sts_credentials)" || true
    if [ -n "$parsed" ]; then
      AWS_SIGV4_KEY="$(printf '%s\n' "$parsed" | sed -n 1p)"
      AWS_SIGV4_SECRET="$(printf '%s\n' "$parsed" | sed -n 2p)"
      AWS_SIGV4_TOKEN="$(printf '%s\n' "$parsed" | sed -n 3p)"
      CRED_SOURCE="irsa-web-identity"; return 0
    fi
    echo "ERROR: sigv4 web-identity (IRSA) credential resolution failed. STS response head:" >&2
    printf '%s' "$resp" | head -c 300 >&2; echo "" >&2
    return 1
  fi

  # 2. ECS task role / EKS Pod Identity — container credentials endpoint (JSON).
  #    ECS sets AWS_CONTAINER_CREDENTIALS_RELATIVE_URI + a direct-value token env;
  #    Pod Identity (AWS's successor to IRSA) sets AWS_CONTAINER_CREDENTIALS_FULL_URI
  #    + a token FILE that rotates, so read the file fresh at resolve time.
  if [ -n "${AWS_CONTAINER_CREDENTIALS_FULL_URI:-}" ] || [ -n "${AWS_CONTAINER_CREDENTIALS_RELATIVE_URI:-}" ]; then
    local ecs_url resp auth_val=""; local hdr=()
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
    resp="$(curl -sS --connect-timeout 3 "${hdr[@]}" "$ecs_url" 2>/dev/null)" || true
    AWS_SIGV4_KEY="$(printf '%s' "$resp" | jq -r '.AccessKeyId // empty' 2>/dev/null)"
    AWS_SIGV4_SECRET="$(printf '%s' "$resp" | jq -r '.SecretAccessKey // empty' 2>/dev/null)"
    AWS_SIGV4_TOKEN="$(printf '%s' "$resp" | jq -r '.Token // empty' 2>/dev/null)"
    if [ -n "$AWS_SIGV4_KEY" ] && [ -n "$AWS_SIGV4_SECRET" ]; then
      CRED_SOURCE="container-credentials"; return 0
    fi
    echo "ERROR: sigv4 container-credentials (ECS / EKS Pod Identity) resolution failed." >&2
    return 1
  fi

  # 3. EC2 instance profile via IMDSv2 (PUT token, then GET creds).
  local imds_token role resp
  imds_token="$(curl -sS -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 300" --connect-timeout 2 2>/dev/null)" || true
  if [ -n "$imds_token" ]; then
    role="$(curl -sS --connect-timeout 2 -H "X-aws-ec2-metadata-token: $imds_token" \
      "http://169.254.169.254/latest/meta-data/iam/security-credentials/" 2>/dev/null)" || true
    if [ -n "$role" ]; then
      resp="$(curl -sS --connect-timeout 2 -H "X-aws-ec2-metadata-token: $imds_token" \
        "http://169.254.169.254/latest/meta-data/iam/security-credentials/${role}" 2>/dev/null)" || true
      AWS_SIGV4_KEY="$(printf '%s' "$resp" | jq -r '.AccessKeyId // empty' 2>/dev/null)"
      AWS_SIGV4_SECRET="$(printf '%s' "$resp" | jq -r '.SecretAccessKey // empty' 2>/dev/null)"
      AWS_SIGV4_TOKEN="$(printf '%s' "$resp" | jq -r '.Token // empty' 2>/dev/null)"
      if [ -n "$AWS_SIGV4_KEY" ] && [ -n "$AWS_SIGV4_SECRET" ]; then
        CRED_SOURCE="ec2-instance-profile"; return 0
      fi
    fi
  fi

  # 4. Static keys — deliberate opt-in escape hatch via LUNAR_SECRET_AWS_*
  #    (NOT ambient AWS_* env). Last resort; these do not self-refresh.
  if [ -n "${LUNAR_SECRET_AWS_ACCESS_KEY_ID:-}" ] && [ -n "${LUNAR_SECRET_AWS_SECRET_ACCESS_KEY:-}" ]; then
    AWS_SIGV4_KEY="${LUNAR_SECRET_AWS_ACCESS_KEY_ID}"
    AWS_SIGV4_SECRET="${LUNAR_SECRET_AWS_SECRET_ACCESS_KEY}"
    AWS_SIGV4_TOKEN="${LUNAR_SECRET_AWS_SESSION_TOKEN:-}"
    CRED_SOURCE="static-keys"; return 0
  fi

  echo "ERROR: auth_mode=sigv4 but no AWS credentials could be resolved." >&2
  echo "  Tried (in order): IRSA / EKS Pod Identity web-identity, ECS / Pod Identity" >&2
  echo "  container credentials, EC2 IMDSv2, then static LUNAR_SECRET_AWS_* keys." >&2
  echo "  Attach an IAM role to the collector's snippet-pod service account (see" >&2
  echo "  README), or set the LUNAR_SECRET_AWS_ACCESS_KEY_ID / _SECRET_ACCESS_KEY secrets." >&2
  return 1
}

# assume_role_chain is the optional aws_assume_role_arns hop, for a gateway that
# only trusts a role the base identity can assume (usually cross-account). The
# first candidate STS accepts replaces the credentials, so one config can span
# environments whose base roles each assume only their own. No DurationSeconds:
# STS's 1h default is the chained-role maximum. ARNs carry an account id, so
# failures are logged by position and STS error code only.
assume_role_chain() {
  local raw=() arns=() arn resp status parsed reason i=0
  local token_hdr=()
  # Commas or whitespace separate entries; an ARN never contains whitespace.
  IFS=',' read -ra raw <<< "${AWS_ASSUME_ROLE_ARNS//[[:space:]]/,}"
  for arn in "${raw[@]}"; do
    if [ -n "$arn" ]; then arns+=("$arn"); fi
  done
  if [ "${#arns[@]}" -eq 0 ]; then return 0; fi

  if [ -n "$AWS_SIGV4_TOKEN" ]; then
    token_hdr=(-H "x-amz-security-token: ${AWS_SIGV4_TOKEN}")
  fi
  for arn in "${arns[@]}"; do
    i=$((i + 1))
    status=0
    resp="$(curl -sS --max-time 15 --get "https://sts.${AWS_SIGV4_REGION}.amazonaws.com/" \
      --aws-sigv4 "aws:amz:${AWS_SIGV4_REGION}:sts" \
      --user "${AWS_SIGV4_KEY}:${AWS_SIGV4_SECRET}" \
      "${token_hdr[@]}" \
      --data-urlencode "Action=AssumeRole" \
      --data-urlencode "Version=2011-06-15" \
      --data-urlencode "RoleArn=${arn}" \
      --data-urlencode "RoleSessionName=lunar-pagerduty-collector" 2>/dev/null)" || status=$?
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
    echo "Backstage auth: aws_assume_role_arns role ${i}/${#arns[@]} not assumed (${reason})" >&2
  done
  echo "ERROR: sts:AssumeRole failed for every role in aws_assume_role_arns. The base identity" >&2
  echo "  (${CRED_SOURCE}) needs sts:AssumeRole on the role, and the role's trust policy must allow it." >&2
  return 1
}

# Percent-encodes a whole query-param or path value. See
# collectors/backstage/main.sh for why the filter grammar's own `=` and `,` go
# encoded too (curl < 8.14 mis-signs a literal `=` under sigv4).
url_escape() { jq -rn --arg s "$1" '$s|@uri'; }

# backstage_setup_auth fills AUTH_ARGS with the curl arguments every lookup
# sends: a Bearer header (bearer) or the SigV4 flags plus session token
# (sigv4). On a config or credential problem it sets LIVE_ERROR and returns 1,
# so the caller falls back to the local file instead of failing the collector.
backstage_setup_auth() {
  AUTH_ARGS=()
  case "$AUTH_MODE" in
    bearer)
      if [ -n "${LUNAR_SECRET_BACKSTAGE_TOKEN:-}" ]; then
        AUTH_ARGS=(-H "Authorization: Bearer ${LUNAR_SECRET_BACKSTAGE_TOKEN}")
      fi
      ;;
    sigv4)
      AWS_SIGV4_REGION="${LUNAR_VAR_AWS_REGION:-${AWS_REGION:-${AWS_DEFAULT_REGION:-}}}"
      AWS_SIGV4_SERVICE="${LUNAR_VAR_AWS_SERVICE:-execute-api}"
      AWS_ASSUME_ROLE_ARNS="${LUNAR_VAR_AWS_ASSUME_ROLE_ARNS:-}"
      if [ -z "$AWS_SIGV4_REGION" ]; then
        LIVE_ERROR="aws_region required for sigv4 (set the aws_region input or the AWS_REGION env var)"
      elif ! resolve_aws_credentials; then
        LIVE_ERROR="sigv4 credential resolution failed"
      elif ! assume_role_chain; then
        LIVE_ERROR="sts:AssumeRole failed for every role in aws_assume_role_arns"
      else
        AUTH_ARGS=(--aws-sigv4 "aws:amz:${AWS_SIGV4_REGION}:${AWS_SIGV4_SERVICE}" \
                   --user "${AWS_SIGV4_KEY}:${AWS_SIGV4_SECRET}")
        if [ -n "${AWS_SIGV4_TOKEN:-}" ]; then
          AUTH_ARGS+=(-H "x-amz-security-token: ${AWS_SIGV4_TOKEN}")
        fi
        echo "Backstage auth: SigV4 (region=$AWS_SIGV4_REGION service=$AWS_SIGV4_SERVICE, credentials via $CRED_SOURCE)" >&2
      fi
      ;;
    *)
      LIVE_ERROR="invalid backstage_auth_mode '$AUTH_MODE' (expected 'bearer' or 'sigv4')"
      ;;
  esac
  if [ -z "$LIVE_ERROR" ]; then
    case "$REF_LOOKUP" in
      by-name|by-query) ;;
      *) LIVE_ERROR="invalid backstage_ref_lookup '$REF_LOOKUP' (expected 'by-name' or 'by-query')" ;;
    esac
  fi
  [ -z "$LIVE_ERROR" ]
}

# backstage_fetch_entity <kind> <namespace> <name> looks one entity up.
# Returns 0 and prints the entity JSON when it exists, 1 when the catalog has
# no such entity, and 2 with the reason on stdout when the lookup couldn't
# complete. A 200 we can't read (a gateway's HTML login page) is a 2, never a
# miss: reading it as "no annotation here" would report a mapping as missing.
backstage_fetch_entity() {
  local kind="$1" ns="$2" name="$3" url response curl_status=0 http_code body entity
  if [ "$REF_LOOKUP" = "by-query" ]; then
    url="${BACKSTAGE_BASE_URL}${BACKSTAGE_API_PATH_PREFIX}/catalog/entities/by-query?limit=1&filter=$(url_escape "kind=${kind},metadata.namespace=${ns},metadata.name=${name}")"
  else
    url="${BACKSTAGE_BASE_URL}${BACKSTAGE_API_PATH_PREFIX}/catalog/entities/by-name/$(url_escape "$kind")/$(url_escape "$ns")/$(url_escape "$name")"
  fi
  response=$(curl -sS -w '\n%{http_code}' --max-time 15 "${AUTH_ARGS[@]}" "$url") || curl_status=$?
  if [ "$curl_status" -ne 0 ]; then
    echo "request failed (curl exit ${curl_status})"
    return 2
  fi
  http_code="${response##*$'\n'}"
  body="${response%$'\n'*}"

  if [ "$REF_LOOKUP" = "by-query" ]; then
    if [ "$http_code" != "200" ]; then
      echo "HTTP ${http_code}"
      return 2
    fi
    if ! printf '%s' "$body" | jq -e '(.items | type) == "array"' >/dev/null 2>&1; then
      echo "unparseable by-query response"
      return 2
    fi
    entity=$(printf '%s' "$body" | jq -c '.items[0] // empty')
    if [ -z "$entity" ]; then
      return 1
    fi
  elif [ "$http_code" = "200" ]; then
    entity="$body"
  elif [ "$http_code" = "404" ]; then
    return 1
  else
    echo "HTTP ${http_code}"
    return 2
  fi

  if ! printf '%s' "$entity" | jq -e 'type == "object" and (.metadata | type) == "object"' >/dev/null 2>&1; then
    echo "unparseable entity response"
    return 2
  fi
  printf '%s' "$entity"
}

# entity_annotation prints the first non-empty value, among the keys in
# $ANNOTATION_KEYS (comma-separated, tried in order), of the entity on stdin.
entity_annotation() {
  jq -r --arg keys "$ANNOTATION_KEYS" '
    ($keys | split(",") | map(gsub("^\\s+|\\s+$"; "")) | map(select(length > 0))) as $ks
    | (.metadata.annotations | if type == "object" then . else {} end) as $a
    | [ $ks[] | $a[.] // "" | tostring | gsub("\\s"; "") | select(. != "") ]
    | (.[0] // "")
  ' 2>/dev/null || :
}

# entity_ref_field <field> prints spec.<field> of the entity on stdin when it
# is a non-empty string.
entity_ref_field() {
  jq -r --arg f "$1" '(.spec | if type == "object" then .[$f] else null end)
    | if type == "string" then . else "" end' 2>/dev/null || :
}

# backstage_live_lookup <namespace> <name> walks Component -> System -> Domain
# from the named Component, stopping at the first entity that carries one of
# the annotation keys. Sets LIVE_ID and LIVE_VIA (the entity ref, e.g.
# system:default/payment-platform) on a hit, or LIVE_ERROR when a lookup
# couldn't complete; a walk that ends without either is a definitive miss.
# Appends every entity it consulted to SEARCHED.
#
# The Component's own annotation wins, so an instance whose processors already
# copy a System's annotation onto its Components answers on the first request.
# Each next hop is read off the entity just fetched, and a bare reference
# resolves against that entity's namespace — Backstage's own rule, the same
# derivation collectors/backstage/main.sh uses for its system -> domain hop.
backstage_live_lookup() {
  local kind="component" ns="$1" name="$2" ref entity rc value next next_ref entity_ns
  LIVE_ID=""
  LIVE_VIA=""
  LIVE_ERROR=""

  if ! backstage_setup_auth; then
    echo "backstage_discovery: live lookup not run: $LIVE_ERROR" >&2
    return 0
  fi

  while :; do
    ref="${kind}:${ns}/${name}"
    rc=0
    entity=$(backstage_fetch_entity "$kind" "$ns" "$name") || rc=$?
    if [ "$rc" -eq 2 ]; then
      LIVE_ERROR="lookup of ${ref} failed: ${entity}"
      echo "backstage_discovery: $LIVE_ERROR" >&2
      return 0
    elif [ "$rc" -ne 0 ]; then
      SEARCHED+=("${ref} (not in catalog)")
      echo "backstage_discovery: ${ref} is not in the catalog" >&2
      return 0
    fi
    SEARCHED+=("$ref")

    value=$(printf '%s' "$entity" | entity_annotation)
    if [ -n "$value" ]; then
      LIVE_ID="$value"
      LIVE_VIA="$ref"
      return 0
    fi

    case "$kind" in
      component) next="system" ;;
      system) next="domain" ;;
      *) return 0 ;;
    esac
    next_ref=$(printf '%s' "$entity" | entity_ref_field "$next")
    if [ -z "$next_ref" ]; then
      return 0
    fi
    entity_ns=$(printf '%s' "$entity" | jq -r '.metadata.namespace // empty' 2>/dev/null || :)
    entity_ns="${entity_ns:-$ns}"

    # Strip an explicit "kind:" prefix, then split an optional "namespace/".
    next_ref="${next_ref#*:}"
    if [[ "$next_ref" == */* ]]; then
      ns="${next_ref%%/*}"
      name="${next_ref#*/}"
    else
      ns="$entity_ns"
      name="$next_ref"
    fi
    kind="$next"
  done
}
