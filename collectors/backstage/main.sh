#!/bin/bash

set -e

SCRIPT_DIR="$(dirname "$0")"

IFS=',' read -ra CANDIDATES <<< "$LUNAR_VAR_PATHS"

CATALOG_FILE=""
for candidate in "${CANDIDATES[@]}"; do
  if [ -f "./$candidate" ]; then
    CATALOG_FILE="./$candidate"
    break
  fi
done

if [ -z "$CATALOG_FILE" ]; then
  # No catalog-info.yaml found — write nothing. Absence of `.catalog.native.backstage`
  # IS the signal. Policies use Check.exists(".catalog.native.backstage") to detect.
  exit 0
fi

PATH_NORMALIZED="${CATALOG_FILE#./}"

YQ_ERR=$(mktemp)
trap 'rm -f "$YQ_ERR"' EXIT

# `catalog-info.yaml` may declare multiple entities separated by `---`. Use
# `yq ea` (eval-all) with `[.]` to collect every document into a single JSON
# array: a plain `yq -o=json '.'` emits the docs as concatenated objects, which
# is not valid JSON and makes the linter choke ("Invalid parser output"),
# false-failing every downstream policy. A single-document file yields a
# one-element array, so the linter's aggregate shape is uniform. Truly malformed
# YAML still exits non-zero and drops to the parse-error branch below.
PARSE_OK=false
if PARSED_JSON=$(yq ea -o=json '[.]' "$CATALOG_FILE" 2>"$YQ_ERR"); then
  RESULT=$(echo "$PARSED_JSON" | python3 "$SCRIPT_DIR/lint_backstage.py" --path "$PATH_NORMALIZED")
  PARSE_OK=true
else
  ERR_MSG=$(tr '\n' ' ' < "$YQ_ERR" | sed 's/[[:space:]]*$//' | head -c 500)
  [ -z "$ERR_MSG" ] && ERR_MSG="YAML parse error"
  RESULT=$(jq -n \
    --arg path "$PATH_NORMALIZED" \
    --arg msg "$ERR_MSG" \
    '{
      valid: false,
      errors: [{line: 0, message: $msg, severity: "error"}],
      path: $path
    }')
fi

# --- Referential integrity (optional) ---
# When backstage_url is configured, cross-check the declared grouping references
# (spec.domain, spec.system) against the live Backstage catalog and record the
# outcome under .refs. `.refs.checked = true` is always written when configured,
# so the policy can distinguish "configured" from "not configured"; a transient
# failure is recorded as {name, error} (rather than omitted) so an outage stays
# distinguishable from a real miss. When backstage_url is unset, nothing is
# written and behavior is identical to a plain parse-and-lint run.
#
# References are resolved from the *primary* entity (the first Component, else
# the first document), which the linter hoists to the top level of $RESULT as
# .spec/.metadata — so we read those here rather than $PARSED_JSON, which is now
# a JSON array of all documents.
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
#
# Deliberately kept in sync with catalogers/backstage/main.sh — both plugins run
# in the same snippet pods under the same service account, so the chain must
# resolve identically. A fix here belongs there too, and vice versa.
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
      --data-urlencode "RoleSessionName=${AWS_ROLE_SESSION_NAME:-lunar-backstage-collector}" \
      --data-urlencode "DurationSeconds=3600" \
      --data-urlencode "WebIdentityToken=${wit}" 2>/dev/null)" || true
    # STS query protocol returns XML; parse with python3 stdlib.
    parsed="$(printf '%s' "$resp" | python3 -c '
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
' 2>/dev/null)" || true
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

BACKSTAGE_URL="${LUNAR_VAR_BACKSTAGE_URL:-}"
if [ "$PARSE_OK" = true ] && [ -n "$BACKSTAGE_URL" ]; then
  BASE_URL="${BACKSTAGE_URL%/}"
  DEFAULT_NS=$(echo "$RESULT" | jq -r '.metadata.namespace // "default"')

  # Path prefix before /catalog/entities — `/api` for a standard Backstage
  # layout, "" for an instance whose catalog API is mounted at the root (e.g.
  # behind an API gateway that strips the `/api` hop, where /api/catalog/…
  # returns 403/404). This matters most under auth_mode: sigv4, since an
  # IAM-fronted Backstage is usually behind Amazon API Gateway — exactly the
  # shape that strips the hop — so leaving this at the default there can 403 on
  # every lookup despite perfectly correct signing.
  # `-` not `:-`: an explicit empty value must survive so it can disable the
  # prefix. The hub always sets LUNAR_VAR_API_PATH_PREFIX — to the manifest
  # default `/api` when unset in config, or the user's value (including "")
  # when set — so `-/api` only fires for a truly-unset var (direct local
  # invocation), not a config-supplied "".
  API_PATH_PREFIX="${LUNAR_VAR_API_PATH_PREFIX-/api}"
  # Normalize: drop any trailing slash, and ensure a non-empty value leads with
  # a slash — so `api`, `/api`, and `/api/` all resolve to `/api`, and "" stays "".
  API_PATH_PREFIX="${API_PATH_PREFIX%/}"
  if [ -n "$API_PATH_PREFIX" ] && [ "${API_PATH_PREFIX#/}" = "$API_PATH_PREFIX" ]; then
    API_PATH_PREFIX="/$API_PATH_PREFIX"
  fi

  # Which catalog endpoint resolves each reference. Both modes produce an
  # identical `.refs` shape, so no policy changes with this input.
  #   by-name  (default) — GET /catalog/entities/by-name/<kind>/<ns>/<name>.
  #                        A direct key lookup whose status IS the answer:
  #                        200 = exists, 404 = miss.
  #   by-query           — GET /catalog/entities/by-query?limit=1&filter=…
  #                        A search, so existence lives in the body rather than
  #                        the status: a 200 with a non-empty `.items` = exists,
  #                        an empty `.items` = miss.
  # by-query is for an instance that only authorizes that endpoint. A gateway in
  # front of Backstage can expose the catalog search API and reject by-name
  # outright, in which case every by-name lookup fails no matter how correct the
  # auth is — the failure mode looks identical to an outage. It is the same
  # endpoint the backstage *cataloger* has always used.
  REF_LOOKUP="${LUNAR_VAR_REF_LOOKUP:-by-name}"

  # --- Authentication ---
  # AUTH_ARGS holds the curl arguments used for every lookup: a Bearer header
  # (bearer mode) or the SigV4 signing flags + session-token header (sigv4).
  # Credentials are resolved ONCE here and reused across both lookups.
  #
  # SETUP_ERROR is the degrade-not-fail channel, and the one deliberate divergence
  # from the cataloger. For the cataloger, fetching the catalog IS the job, so it
  # exits non-zero when credentials can't be resolved. Here, referential integrity
  # is an optional add-on layered on parse-and-lint: discarding valid lint results
  # over an auth misconfiguration would regress the collector's primary function.
  # So a config/credential problem is logged to stderr and recorded per-reference
  # as {name, error} — which the policy already reads as "couldn't determine"
  # rather than "doesn't exist" — and the parse/lint output is always written.
  AUTH_ARGS=()
  SETUP_ERROR=""
  AUTH_MODE="${LUNAR_VAR_AUTH_MODE:-bearer}"

  case "$AUTH_MODE" in
    bearer)
      if [ -n "${LUNAR_SECRET_BACKSTAGE_TOKEN:-}" ]; then
        AUTH_ARGS=(-H "Authorization: Bearer ${LUNAR_SECRET_BACKSTAGE_TOKEN}")
      fi
      ;;
    sigv4)
      AWS_SIGV4_REGION="${LUNAR_VAR_AWS_REGION:-${AWS_REGION:-${AWS_DEFAULT_REGION:-}}}"
      AWS_SIGV4_SERVICE="${LUNAR_VAR_AWS_SERVICE:-execute-api}"
      if [ -z "$AWS_SIGV4_REGION" ]; then
        SETUP_ERROR="aws_region required for sigv4"
        echo "ERROR: $SETUP_ERROR (set the aws_region input or the AWS_REGION env var)" >&2
      elif ! resolve_aws_credentials; then
        SETUP_ERROR="sigv4 credential resolution failed"
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
      SETUP_ERROR="invalid auth_mode '$AUTH_MODE' (expected 'bearer' or 'sigv4')"
      echo "ERROR: $SETUP_ERROR" >&2
      ;;
  esac

  # Validated after auth so that when both are misconfigured the auth problem —
  # the more fundamental one — keeps its more specific message.
  if [ -z "$SETUP_ERROR" ]; then
    case "$REF_LOOKUP" in
      by-name|by-query) ;;
      *)
        SETUP_ERROR="invalid ref_lookup '$REF_LOOKUP' (expected 'by-name' or 'by-query')"
        echo "ERROR: $SETUP_ERROR" >&2
        ;;
    esac
  fi

  # Percent-encode one by-query filter value. A valid Backstage name or
  # namespace (`[A-Za-z0-9][A-Za-z0-9._-]*`) contains nothing @uri escapes, so a
  # legitimate reference goes on the wire byte-for-byte as written. It matters
  # for the illegitimate ones, which is exactly what this feature is asked to
  # detect: a hand-written catalog-info.yaml can declare
  # `spec.domain: "a&filter=kind=system"`, and unencoded that would inject a
  # second filter parameter — Backstage ORs filter params, so a miss could come
  # back as a hit on an unrelated entity. Encoding keeps a bogus reference a
  # miss (or, under sigv4, a signature rejection recorded as {name, error});
  # either way never a false `exists: true`.
  url_escape() { jq -rn --arg s "$1" '$s|@uri'; }

  resolve_ref() {
    # $1 = Backstage kind (domain|system); $2 = declared reference value.
    # Emits a JSON object: {name, exists} on a definitive answer, or
    # {name, error} on a non-definitive outcome — a transient failure
    # (connection error / 5xx) or a config problem that stopped us issuing a
    # meaningful request at all (see SETUP_ERROR above).
    #
    # Side effect: on a definitive hit the resolved entity's JSON is written to
    # $ENTITY_BODY_FILE, so the caller can read fields off the entity it just
    # confirmed (the system -> spec.domain hop below). A *file* is the channel
    # because resolve_ref is always invoked as `$(resolve_ref ...)` — a command
    # substitution runs in a subshell, so a variable assigned here would be
    # discarded on return and the hop would silently never fire. The file is
    # truncated on entry so a previous lookup's entity can never be misread as
    # this one's.
    local kind="$1" value="$2" ref ns name http_code curl_status response body item_count

    : > "$ENTITY_BODY_FILE"

    # Setup never completed (bad auth_mode or ref_lookup, missing aws_region,
    # unresolvable credentials). Report it per-reference instead of firing a
    # request we know cannot succeed — and without discarding the parse/lint
    # results.
    if [ -n "$SETUP_ERROR" ]; then
      jq -n --arg name "$value" --arg err "$SETUP_ERROR" '{name: $name, error: $err}'
      return 0
    fi

    # Strip an explicit "kind:" prefix, then split an optional "namespace/"
    # prefix; a bare value uses the component's namespace (falling back to
    # "default"). Mirrors Backstage's own reference resolution.
    ref="${value#*:}"
    if [[ "$ref" == */* ]]; then
      ns="${ref%%/*}"
      name="${ref#*/}"
    else
      ns="$DEFAULT_NS"
      name="$ref"
    fi

    set +e
    if [ "$REF_LOOKUP" = "by-query" ]; then
      # by-query needs the response *body* (existence is `.items`, not the
      # status), so `-w '\n%{http_code}'` appends the status after it and one
      # request yields both. `limit=1` — we only ask whether anything matches.
      # Commas and `=` stay literal: they are this endpoint's own filter
      # grammar (comma = AND), and it is the wire form the cataloger has always
      # sent. Only the two interpolated values are escaped.
      response=$(curl -sS -w '\n%{http_code}' --max-time 15 \
        "${AUTH_ARGS[@]}" \
        "${BASE_URL}${API_PATH_PREFIX}/catalog/entities/by-query?limit=1&filter=kind=${kind},metadata.namespace=$(url_escape "$ns"),metadata.name=$(url_escape "$name")")
      curl_status=$?
      http_code="${response##*$'\n'}"
      body="${response%$'\n'*}"
    else
      # by-name's status alone is the existence answer, but the body carries the
      # resolved entity — which the system -> spec.domain hop needs — so keep it
      # instead of discarding it to /dev/null. Same `-w '\n%{http_code}'` shape
      # as the by-query branch, so one request still yields body and status.
      response=$(curl -sS -w '\n%{http_code}' --max-time 15 \
        "${AUTH_ARGS[@]}" \
        "${BASE_URL}${API_PATH_PREFIX}/catalog/entities/by-name/${kind}/${ns}/${name}")
      curl_status=$?
      http_code="${response##*$'\n'}"
      body="${response%$'\n'*}"
    fi
    set -e

    if [ "$curl_status" -ne 0 ]; then
      jq -n --arg name "$value" --arg err "request failed (curl exit ${curl_status})" \
        '{name: $name, error: $err}'
    elif [ "$REF_LOOKUP" = "by-query" ]; then
      # A search reports "no match" as an empty result set, so only a 200 is
      # meaningful and the body decides. A 200 we cannot parse (an HTML login
      # page from a gateway, a truncated response) is NOT a miss: inferring
      # "doesn't exist" from a response we couldn't read would turn our own
      # misconfiguration into a policy failure against the user's file.
      if [ "$http_code" != "200" ]; then
        jq -n --arg name "$value" --arg err "HTTP ${http_code}" '{name: $name, error: $err}'
      elif ! item_count=$(printf '%s' "$body" \
             | jq -e 'if (.items | type) == "array" then (.items | length) else null end' 2>/dev/null); then
        jq -n --arg name "$value" --arg err "unparseable by-query response" \
          '{name: $name, error: $err}'
      elif [ "$item_count" -gt 0 ]; then
        printf '%s' "$body" | jq -c '.items[0]' > "$ENTITY_BODY_FILE" 2>/dev/null || :
        jq -n --arg name "$value" '{name: $name, exists: true}'
      else
        jq -n --arg name "$value" '{name: $name, exists: false}'
      fi
    elif [ "$http_code" = "200" ]; then
      printf '%s' "$body" > "$ENTITY_BODY_FILE"
      jq -n --arg name "$value" '{name: $name, exists: true}'
    elif [ "$http_code" = "404" ]; then
      jq -n --arg name "$value" '{name: $name, exists: false}'
    else
      jq -n --arg name "$value" --arg err "HTTP ${http_code}" '{name: $name, error: $err}'
    fi
  }

  REFS='{"checked":true}'

  # Scratch file resolve_ref writes the resolved entity to; see the note there
  # for why this can't be a variable.
  ENTITY_BODY_FILE=$(mktemp)
  trap 'rm -f "$YQ_ERR" "$ENTITY_BODY_FILE"' EXIT

  DOMAIN_REF=$(echo "$RESULT" | jq -r '.spec.domain // empty')
  if [ -n "$DOMAIN_REF" ]; then
    DOMAIN_ENTRY=$(resolve_ref domain "$DOMAIN_REF")
    REFS=$(echo "$REFS" | jq --argjson d "$DOMAIN_ENTRY" '. + {domain: $d}')
  fi

  SYSTEM_REF=$(echo "$RESULT" | jq -r '.spec.system // empty')
  if [ -n "$SYSTEM_REF" ]; then
    SYSTEM_ENTRY=$(resolve_ref system "$SYSTEM_REF")
    REFS=$(echo "$REFS" | jq --argjson s "$SYSTEM_ENTRY" '. + {system: $s}')

    # Transitive hop: component -> its system -> that system's domain.
    #
    # A Component has no domain of its own in the Backstage model — domain
    # membership is a property of the System it belongs to (`System.spec.domain`
    # is what produces the `partOf -> domain:...` relation; a `spec.domain`
    # written on a Component is inert and Backstage generates nothing from it).
    # So for the ordinary one-Component-per-repo file, "is my domain real?"
    # can only be answered through the system, which is what this records at
    # `.refs.system_domain`. `.refs.domain` keeps its existing meaning: the
    # domain THIS entity declares directly (a `kind: System` catalog file).
    #
    # Only hop on a confirmed system: if the system is missing or its lookup
    # errored there is no entity to read a domain off, and reporting a second
    # failure for the same root cause would just double the noise.
    #
    # Belt-and-braces: resolve_ref only writes the body on a definitive hit and
    # truncates on entry, so today a non-existent system already leaves the file
    # empty and the hop would no-op anyway. The explicit guard states the
    # invariant so that stays true if resolve_ref ever starts capturing error
    # bodies too.
    if [ "$(echo "$SYSTEM_ENTRY" | jq -r '.exists // false')" = "true" ]; then
      SYSTEM_DOMAIN_REF=$(jq -r '.spec.domain // empty' "$ENTITY_BODY_FILE" 2>/dev/null || :)
      if [ -n "$SYSTEM_DOMAIN_REF" ]; then
        # A bare reference on the System resolves against the SYSTEM's namespace,
        # not the component's — they can differ — so borrow it for this lookup.
        # (Backstage normalizes metadata.namespace on read, so it is present;
        # fall back to the component's namespace if an instance ever omits it.)
        SYSTEM_NS=$(jq -r '.metadata.namespace // empty' "$ENTITY_BODY_FILE" 2>/dev/null || :)
        SAVED_DEFAULT_NS="$DEFAULT_NS"
        DEFAULT_NS="${SYSTEM_NS:-$DEFAULT_NS}"
        SYSTEM_DOMAIN_ENTRY=$(resolve_ref domain "$SYSTEM_DOMAIN_REF")
        DEFAULT_NS="$SAVED_DEFAULT_NS"
        # Carry the system that pointed here: the entity to fix lives in the
        # System's own catalog file, which is usually another team's repo, so a
        # bare domain name would not tell anyone where to go.
        SYSTEM_DOMAIN_ENTRY=$(echo "$SYSTEM_DOMAIN_ENTRY" \
          | jq --arg via "$SYSTEM_REF" '. + {via_system: $via}')
        REFS=$(echo "$REFS" | jq --argjson sd "$SYSTEM_DOMAIN_ENTRY" '. + {system_domain: $sd}')
      fi
    fi
  fi

  RESULT=$(echo "$RESULT" | jq --argjson refs "$REFS" '. + {refs: $refs}')
fi

echo "$RESULT" | lunar collect -j ".catalog.native.backstage" -
