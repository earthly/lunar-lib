#!/bin/bash
#
# Backstage Cataloger — sync entities from a Backstage instance into Lunar.
#
# Fetches <api_path_prefix>/catalog/entities (paginated), routes:
#   - Component, API, Resource → .components (keyed by <id_prefix><annotation value>)
#   - Domain, System          → .domains    (keyed by metadata.name)
# Applies owner_format (as-is | bare-name), derived bs-type-*/bs-lifecycle-*
# tags, default_owner fallback, and an optional Backstage filter expression.
#
# Inputs (LUNAR_VAR_*):
#   backstage_url             (required) Base URL of the Backstage instance
#   api_path_prefix           (default /api) Path prefix before /catalog/entities;
#                             set to "" for a Backstage API mounted at the root
#   entity_kinds              (default Component,Domain) Comma-separated kinds
#   namespace                 (default default) Namespace, or "*" for all
#   component_id_annotation   (default github.com/project-slug)
#   component_id_prefix       (default github.com/)
#   tag_prefix                (default bs-)
#   include_derived_tags      (default true)
#   owner_format              (default as-is) as-is | bare-name
#   default_owner             (default empty)
#   domain_default_description (default empty)
#   filter                    (default empty) Raw Backstage filter clause
#   include_types / exclude_types            (default empty) spec.type allow/deny
#   include_lifecycles / exclude_lifecycles  (default empty) spec.lifecycle allow/deny
#   include_domains / exclude_domains        (default empty) resolved-domain-path allow/deny
#   include_systems / exclude_systems        (default empty) spec.system allow/deny
#     Structured filters run client-side: empty=off, exclude wins over include,
#     case-insensitive. type/lifecycle pass entities lacking the field;
#     domain/system include is membership (no value = not a member = excluded).
#   auth_mode                 (default bearer) bearer | sigv4
#   aws_region                (sigv4 only; falls back to AWS_REGION env)
#   aws_service               (sigv4 only; default execute-api)
#   verify_repos              (default true) drop components whose repo does not exist
#   github_api_url            (default https://api.github.com) REST base for verification
#
# Secrets:
#   LUNAR_SECRET_BACKSTAGE_TOKEN   (bearer mode; sent as Bearer if present)
#   LUNAR_SECRET_GH_TOKEN          (optional; enables repo-existence verification)
#   LUNAR_SECRET_AWS_ACCESS_KEY_ID / _SECRET_ACCESS_KEY / _SESSION_TOKEN
#     (sigv4 mode; optional static-key escape hatch, tried LAST — role-based
#      creds (IRSA / Pod Identity / ECS / EC2) are preferred and self-refresh)

set -euo pipefail

BACKSTAGE_URL="${LUNAR_VAR_BACKSTAGE_URL:?backstage_url input is required}"
BACKSTAGE_URL="${BACKSTAGE_URL%/}"

# Path prefix prepended before `/catalog/entities`. Defaults to `/api` (the
# standard Backstage layout). Set to "" for an instance whose catalog API is
# mounted at the root — e.g. behind an API gateway that strips the `/api` hop.
# `-` not `:-` (same treatment as TAG_PREFIX below): an explicit empty value
# must survive so it can disable the prefix. The hub always sets
# LUNAR_VAR_API_PATH_PREFIX — to the manifest default `/api` when unset in
# config, or the user's value (including "") when set — so `-/api` only fires
# for a truly-unset var (direct local invocation), not a config-supplied "".
API_PATH_PREFIX="${LUNAR_VAR_API_PATH_PREFIX-/api}"
# Normalize: drop any trailing slash, and ensure a non-empty value leads with a
# slash — so `api`, `/api`, and `/api/` all resolve to `/api`, and "" stays "".
API_PATH_PREFIX="${API_PATH_PREFIX%/}"
if [ -n "$API_PATH_PREFIX" ] && [ "${API_PATH_PREFIX#/}" = "$API_PATH_PREFIX" ]; then
    API_PATH_PREFIX="/$API_PATH_PREFIX"
fi

ENTITY_KINDS="${LUNAR_VAR_ENTITY_KINDS:-Component,Domain}"
NAMESPACE="${LUNAR_VAR_NAMESPACE:-default}"
COMPONENT_ID_ANNOTATION="${LUNAR_VAR_COMPONENT_ID_ANNOTATION:-github.com/project-slug}"
COMPONENT_ID_PREFIX="${LUNAR_VAR_COMPONENT_ID_PREFIX:-github.com/}"
# `-` not `:-`: an explicit empty tag_prefix must survive so it can disable
# prefixing (documented behavior). The hub always sets LUNAR_VAR_TAG_PREFIX —
# to the manifest default `bs-` when unset in config, or to the user's value
# (including "") when set — so `-bs-` only fires for a truly-unset var (direct
# local invocation), not for a config-supplied empty string.
TAG_PREFIX="${LUNAR_VAR_TAG_PREFIX-bs-}"
INCLUDE_DERIVED_TAGS="${LUNAR_VAR_INCLUDE_DERIVED_TAGS:-true}"
OWNER_FORMAT="${LUNAR_VAR_OWNER_FORMAT:-as-is}"
DEFAULT_OWNER="${LUNAR_VAR_DEFAULT_OWNER:-}"
DOMAIN_DEFAULT_DESCRIPTION="${LUNAR_VAR_DOMAIN_DEFAULT_DESCRIPTION:-}"
USER_FILTER="${LUNAR_VAR_FILTER:-}"

# Structured client-side include/exclude filters (comma-separated; empty = off).
# Applied after the fetch during the component transform: exclude wins over
# include, matching is case-insensitive. See the "Client-side filtering" block
# below the fetch for the exact semantics.
INCLUDE_TYPES="${LUNAR_VAR_INCLUDE_TYPES:-}"
EXCLUDE_TYPES="${LUNAR_VAR_EXCLUDE_TYPES:-}"
INCLUDE_LIFECYCLES="${LUNAR_VAR_INCLUDE_LIFECYCLES:-}"
EXCLUDE_LIFECYCLES="${LUNAR_VAR_EXCLUDE_LIFECYCLES:-}"
INCLUDE_DOMAINS="${LUNAR_VAR_INCLUDE_DOMAINS:-}"
EXCLUDE_DOMAINS="${LUNAR_VAR_EXCLUDE_DOMAINS:-}"
INCLUDE_SYSTEMS="${LUNAR_VAR_INCLUDE_SYSTEMS:-}"
EXCLUDE_SYSTEMS="${LUNAR_VAR_EXCLUDE_SYSTEMS:-}"

VERIFY_REPOS="${LUNAR_VAR_VERIFY_REPOS:-true}"
GITHUB_API_URL="${LUNAR_VAR_GITHUB_API_URL:-https://api.github.com}"
GITHUB_API_URL="${GITHUB_API_URL%/}"

PAGE_SIZE="${PAGE_SIZE:-200}"
MAX_RETRIES="${MAX_RETRIES:-5}"
INITIAL_BACKOFF="${INITIAL_BACKOFF:-5}"
BATCH_SIZE="${BATCH_SIZE:-1000}"
# Repos checked per GraphQL request. One aliased `repository(owner:,name:)` field
# per repo; GitHub prices a query by nodes returned, so 100 repos cost ~1 rate
# limit point instead of the 100 REST calls the same check would take.
VERIFY_BATCH_SIZE="${VERIFY_BATCH_SIZE:-100}"

AUTH_MODE="${LUNAR_VAR_AUTH_MODE:-bearer}"

# --- Authentication -------------------------------------------------------
# AUTH_ARGS holds the curl arguments used for every request: a Bearer header
# (bearer mode) or the SigV4 signing flags + session-token header (sigv4).
# For sigv4 we resolve credentials ONCE here and reuse them for all pages —
# temporary role credentials last well beyond a single catalog walk, and each
# scheduled run re-resolves fresh ones (self-refreshing, nothing to rotate).
AUTH_ARGS=()

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
        local wit resp
        wit="$(cat "$AWS_WEB_IDENTITY_TOKEN_FILE")"
        resp="$(curl -sS -X POST "https://sts.${AWS_SIGV4_REGION}.amazonaws.com/" \
            --data-urlencode "Action=AssumeRoleWithWebIdentity" \
            --data-urlencode "Version=2011-06-15" \
            --data-urlencode "RoleArn=${AWS_ROLE_ARN}" \
            --data-urlencode "RoleSessionName=${AWS_ROLE_SESSION_NAME:-lunar-backstage-cataloger}" \
            --data-urlencode "DurationSeconds=3600" \
            --data-urlencode "WebIdentityToken=${wit}" 2>/dev/null)" || true
        # STS query protocol returns XML; parse with python3 stdlib.
        local parsed
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
    echo "  Attach an IAM role to the cataloger's snippet-pod service account (see" >&2
    echo "  README), or set the LUNAR_SECRET_AWS_ACCESS_KEY_ID / _SECRET_ACCESS_KEY secrets." >&2
    return 1
}

case "$AUTH_MODE" in
    bearer)
        if [ -n "${LUNAR_SECRET_BACKSTAGE_TOKEN:-}" ]; then
            AUTH_ARGS=(-H "Authorization: Bearer $LUNAR_SECRET_BACKSTAGE_TOKEN")
        fi
        ;;
    sigv4)
        AWS_SIGV4_REGION="${LUNAR_VAR_AWS_REGION:-${AWS_REGION:-${AWS_DEFAULT_REGION:-}}}"
        AWS_SIGV4_SERVICE="${LUNAR_VAR_AWS_SERVICE:-execute-api}"
        if [ -z "$AWS_SIGV4_REGION" ]; then
            echo "ERROR: aws_region required for sigv4 (set the aws_region input or the AWS_REGION env var)" >&2
            exit 1
        fi
        if ! resolve_aws_credentials; then
            exit 1
        fi
        AUTH_ARGS=(--aws-sigv4 "aws:amz:${AWS_SIGV4_REGION}:${AWS_SIGV4_SERVICE}" \
                   --user "${AWS_SIGV4_KEY}:${AWS_SIGV4_SECRET}")
        if [ -n "${AWS_SIGV4_TOKEN:-}" ]; then
            AUTH_ARGS+=(-H "x-amz-security-token: ${AWS_SIGV4_TOKEN}")
        fi
        ;;
    *)
        echo "ERROR: invalid auth_mode '$AUTH_MODE' (expected 'bearer' or 'sigv4')" >&2
        exit 1
        ;;
esac

echo "Cataloging Backstage entities from: $BACKSTAGE_URL${API_PATH_PREFIX}/catalog/entities"
if [ "$AUTH_MODE" = "sigv4" ]; then
    echo "Auth: SigV4 (region=$AWS_SIGV4_REGION service=$AWS_SIGV4_SERVICE, credentials via $CRED_SOURCE)"
else
    echo "Auth: bearer${LUNAR_SECRET_BACKSTAGE_TOKEN:+ (token set)}"
fi
echo "Kinds: $ENTITY_KINDS"
echo "Namespace: $NAMESPACE"
echo "Component id: $COMPONENT_ID_PREFIX + <annotation '$COMPONENT_ID_ANNOTATION'>"
echo "Tag prefix: $TAG_PREFIX (derived: $INCLUDE_DERIVED_TAGS)"
echo "Owner format: $OWNER_FORMAT"
[ -n "$DEFAULT_OWNER" ] && echo "Default owner: $DEFAULT_OWNER"
[ -n "$USER_FILTER" ] && echo "Extra filter: $USER_FILTER"
[ -n "$INCLUDE_TYPES" ]      && echo "include_types: $INCLUDE_TYPES"
[ -n "$EXCLUDE_TYPES" ]      && echo "exclude_types: $EXCLUDE_TYPES"
[ -n "$INCLUDE_LIFECYCLES" ] && echo "include_lifecycles: $INCLUDE_LIFECYCLES"
[ -n "$EXCLUDE_LIFECYCLES" ] && echo "exclude_lifecycles: $EXCLUDE_LIFECYCLES"
[ -n "$INCLUDE_DOMAINS" ]    && echo "include_domains: $INCLUDE_DOMAINS"
[ -n "$EXCLUDE_DOMAINS" ]    && echo "exclude_domains: $EXCLUDE_DOMAINS"
[ -n "$INCLUDE_SYSTEMS" ]    && echo "include_systems: $INCLUDE_SYSTEMS"
[ -n "$EXCLUDE_SYSTEMS" ]    && echo "exclude_systems: $EXCLUDE_SYSTEMS"

# --- Build filter query --------------------------------------------------
# Backstage semantics: multiple ?filter= params are OR'd; commas within a
# single filter are AND'd. We want (kind=X OR kind=Y) AND namespace AND user
# filter — i.e. include namespace + user filter in every kind clause.
FILTER_QUERY=""
IFS=',' read -ra KIND_ARRAY <<< "$ENTITY_KINDS"
for kind in "${KIND_ARRAY[@]}"; do
    kind=$(echo "$kind" | xargs)
    [ -z "$kind" ] && continue

    CLAUSE="kind=$kind"
    if [ "$NAMESPACE" != "*" ] && [ -n "$NAMESPACE" ]; then
        CLAUSE="$CLAUSE,metadata.namespace=$NAMESPACE"
    fi
    if [ -n "$USER_FILTER" ]; then
        CLAUSE="$CLAUSE,$USER_FILTER"
    fi
    FILTER_QUERY="${FILTER_QUERY}&filter=$CLAUSE"
done

# --- Paginated fetch -----------------------------------------------------
fetch_page() {
    local cursor="$1"
    local url="$BACKSTAGE_URL${API_PATH_PREFIX}/catalog/entities/by-query?limit=$PAGE_SIZE${cursor:+&cursor=$cursor}$FILTER_QUERY"

    local attempt=1
    local backoff=$INITIAL_BACKOFF
    while [ "$attempt" -le "$MAX_RETRIES" ]; do
        local response_file
        response_file=$(mktemp)
        local http_status
        http_status=$(curl -sS -o "$response_file" -w '%{http_code}' \
            "${AUTH_ARGS[@]}" \
            -H "Accept: application/json" \
            "$url" 2>/dev/null || echo "000")
        local body
        body=$(cat "$response_file")
        rm -f "$response_file"

        if [ "$http_status" = "200" ]; then
            echo "$body"
            return 0
        fi

        if [ "$http_status" = "429" ] || [[ "$http_status" =~ ^5 ]] || [ "$http_status" = "000" ]; then
            echo "Transient $http_status from Backstage (attempt $attempt/$MAX_RETRIES, cursor=$cursor), waiting ${backoff}s..." >&2
            sleep "$backoff"
            backoff=$((backoff * 2))
            attempt=$((attempt + 1))
            continue
        fi

        echo "Error from Backstage ($http_status) at cursor=$cursor:" >&2
        echo "$body" | head -c 500 >&2
        echo "" >&2
        return 1
    done
    echo "Failed to fetch page at cursor=$cursor after $MAX_RETRIES attempts" >&2
    return 1
}

ALL_ENTITIES=$(mktemp)
trap 'rm -f "$ALL_ENTITIES" "${ALL_ENTITIES}.chunk" "${ALL_ENTITIES}.new" "${ALL_ENTITIES}.entries"' EXIT
echo "[]" > "$ALL_ENTITIES"

CURSOR=""
TOTAL_FETCHED=0
while true; do
    RESPONSE=$(fetch_page "$CURSOR")
    PAGE=$(echo "$RESPONSE" | jq '.items')
    PAGE_COUNT=$(echo "$PAGE" | jq 'length')

    if [ "$PAGE_COUNT" -eq 0 ]; then
        break
    fi

    echo "$PAGE" > "${ALL_ENTITIES}.chunk"
    jq -s 'add' "$ALL_ENTITIES" "${ALL_ENTITIES}.chunk" > "${ALL_ENTITIES}.new"
    mv "${ALL_ENTITIES}.new" "$ALL_ENTITIES"
    rm -f "${ALL_ENTITIES}.chunk"

    TOTAL_FETCHED=$((TOTAL_FETCHED + PAGE_COUNT))
    echo "  fetched cursor=${CURSOR:-start} page=$PAGE_COUNT total=$TOTAL_FETCHED"

    NEXT_CURSOR=$(echo "$RESPONSE" | jq -r '.pageInfo.nextCursor // empty')
    if [ -z "$NEXT_CURSOR" ]; then
        break
    fi
    CURSOR="$NEXT_CURSOR"
done

echo "Total entities fetched: $TOTAL_FETCHED"

if [ "$TOTAL_FETCHED" -eq 0 ]; then
    echo "No Backstage entities matched the filter; nothing to write"
    exit 0
fi

# --- Resolve nested domain paths -----------------------------------------
# Lunar encodes domain hierarchy as dotted names (a.b.c is a child of a.b), so
# translate Backstage's reference-based nesting into dotted keys:
#   - a Domain's key is its full spec.subdomainOf ancestry (a.b.c)
#   - a System is nested under the domain it belongs to (spec.domain):
#     <domain-path>.<system-name>
# Parent resolution only sees fetched entities; a reference to an un-synced
# parent contributes its bare name as one segment and stops the walk there.
# Cycles are broken defensively so a malformed catalog can't hang the run.
# Produces {domains: {name: path}, systems: {name: path}} for the transforms
# below to look up.
PATHS=$(jq '
    def bare(s):
        if (s | type) != "string" or s == "" then s
        elif (s | contains("/")) then (s | split("/") | last)
        else s
        end;

    ( [ .[] | select(.kind == "Domain")
        | { key: (.metadata.name | tostring),
            value: ((.spec.subdomainOf // "") | tostring | if . == "" then null else bare(.) end) } ]
      | from_entries ) as $domain_parent
    | ( [ .[] | select(.kind == "System")
          | { key: (.metadata.name | tostring),
              value: ((.spec.domain // "") | tostring | if . == "" then null else bare(.) end) } ]
        | from_entries ) as $system_parent
    | ( def dpath($n; $seen):
          if $n == null or $n == "" then []
          elif ($seen | index($n)) then []
          else ($domain_parent[$n] // null) as $p
               | (if $p == null then [$n] else dpath($p; $seen + [$n]) + [$n] end)
          end;
        {
          domains: ( [ $domain_parent | keys[] as $k
                       | { key: $k, value: (dpath($k; []) | join(".")) } ] | from_entries ),
          systems: ( [ $system_parent | to_entries[] | .key as $k | (.value) as $dom
                       | { key: $k,
                           value: (if $dom == null then $k
                                   else (dpath($dom; []) | join(".")) as $dp
                                        | (if $dp == "" then $k else $dp + "." + $k end)
                                   end) } ] | from_entries )
        } )
    ' "$ALL_ENTITIES")

# --- Transform to Lunar catalog entries ----------------------------------
# Components from Component / API / Resource keyed by <prefix><annotation>; a
# component's domain is the nested dotted path of its spec.system (else
# spec.domain). Domains from Domain / System keyed by their nested dotted path.
COMPONENTS=$(jq \
    --argjson paths "$PATHS" \
    --arg annotation "$COMPONENT_ID_ANNOTATION" \
    --arg id_prefix "$COMPONENT_ID_PREFIX" \
    --arg tag_prefix "$TAG_PREFIX" \
    --arg include_derived "$INCLUDE_DERIVED_TAGS" \
    --arg owner_format "$OWNER_FORMAT" \
    --arg default_owner "$DEFAULT_OWNER" \
    --arg inc_types "$INCLUDE_TYPES" --arg exc_types "$EXCLUDE_TYPES" \
    --arg inc_lifecycles "$INCLUDE_LIFECYCLES" --arg exc_lifecycles "$EXCLUDE_LIFECYCLES" \
    --arg inc_domains "$INCLUDE_DOMAINS" --arg exc_domains "$EXCLUDE_DOMAINS" \
    --arg inc_systems "$INCLUDE_SYSTEMS" --arg exc_systems "$EXCLUDE_SYSTEMS" \
    '
    def bare(s):
        if (s | type) != "string" or s == "" then s
        elif (s | contains("/")) then (s | split("/") | last)
        else s
        end;

    def format_owner(o):
        if $owner_format == "bare-name" then bare(o) else o end;

    def domain_ref(e):
        (e.spec.domain // "") as $d
        | (e.spec.system // "") as $s
        | if ($s | tostring | length) > 0 then
            (bare($s | tostring)) as $sn | ($paths.systems[$sn] // $sn)
          elif ($d | tostring | length) > 0 then
            (bare($d | tostring)) as $dn | ($paths.domains[$dn] // $dn)
          else ""
          end;

    # --- Structured include/exclude filters (client-side) ---
    # empty list = off; exclude wins over include; matching is case-insensitive.
    def toset($csv):
        [ $csv | split(",")[] | gsub("^[ \t]+|[ \t]+$"; "") | select(length > 0) | ascii_downcase ];

    # Attribute filter (type / lifecycle): an entity with NO value for the field
    # is unaffected (passes) — this kind-awareness keeps a lifecycle filter from
    # dropping a Resource, and type/lifecycle filters from touching kinds that
    # lack those fields.
    def keep_attr($v; $inc; $exc):
        ($v // "" | tostring) as $s
        | if ($s | length) == 0 then true
          else ($s | ascii_downcase) as $n
            | if   ($exc | length) > 0 and ((toset($exc) | index($n)) != null) then false
              elif ($inc | length) > 0 and ((toset($inc) | index($n)) == null) then false
              else true end
          end;

    # Domain membership filter: match the resolved dotted path exactly or as a
    # dotted-prefix ancestor (commerce matches commerce.checkout.orders...). For
    # INCLUDE, a component with no resolved domain is not a member -> excluded.
    def dom_hit($p; $csv):
        (toset($csv)) as $set
        | ($set | length) > 0 and ($set | any(. as $v | $p == $v or ($p | startswith($v + "."))));
    def keep_domain($path; $inc; $exc):
        ($path // "" | tostring | ascii_downcase) as $p
        | if   ($exc | length) > 0 and ($p | length) > 0 and dom_hit($p; $exc) then false
          elif ($inc | length) > 0 and (($p | length) == 0 or (dom_hit($p; $inc) | not)) then false
          else true end;

    # System membership filter: exact match on the bare system name. For
    # INCLUDE, a component with no system is not a member -> excluded.
    def keep_system($sys; $inc; $exc):
        (bare($sys // "" | tostring) | ascii_downcase) as $s
        | if   ($exc | length) > 0 and ($s | length) > 0 and ((toset($exc) | index($s)) != null) then false
          elif ($inc | length) > 0 and (($s | length) == 0 or ((toset($inc) | index($s)) == null)) then false
          else true end;

    [.[]
     | select(.kind == "Component" or .kind == "API" or .kind == "Resource")
     | . as $e
     | (.metadata.annotations // {}) as $ann
     | ($ann[$annotation] // "") as $ann_val
     | select(($ann_val | tostring | length) > 0)
     | ($id_prefix + ($ann_val | tostring)) as $id
     | (.spec.owner // "" | tostring) as $raw_owner
     | (if $raw_owner == "" then $default_owner else format_owner($raw_owner) end) as $owner
     | (.metadata.tags // []) as $base_tags
     | ($base_tags | map($tag_prefix + .)) as $prefixed
     | (if $include_derived == "true"
        then ((if ((.spec.type // "") | tostring | length) > 0
                then [$tag_prefix + "type-" + (.spec.type | tostring)] else [] end)
              + (if ((.spec.lifecycle // "") | tostring | length) > 0
                 then [$tag_prefix + "lifecycle-" + (.spec.lifecycle | tostring)] else [] end))
        else []
        end) as $derived
     | domain_ref($e) as $domain
     | select(keep_attr(.spec.type;      $inc_types;      $exc_types))
     | select(keep_attr(.spec.lifecycle; $inc_lifecycles; $exc_lifecycles))
     | select(keep_domain($domain;       $inc_domains;    $exc_domains))
     | select(keep_system(.spec.system;  $inc_systems;    $exc_systems))
     | {key: $id, value:
         ({tags: ($prefixed + $derived)}
          + (if $owner != "" then {owner: $owner} else {} end)
          + (if $domain != "" then {domain: $domain} else {} end))}
    ]
    | from_entries' "$ALL_ENTITIES")

DOMAINS=$(jq \
    --argjson paths "$PATHS" \
    --arg owner_format "$OWNER_FORMAT" \
    --arg default_owner "$DEFAULT_OWNER" \
    --arg default_desc "$DOMAIN_DEFAULT_DESCRIPTION" \
    '
    def bare(s):
        if (s | type) != "string" or s == "" then s
        elif (s | contains("/")) then (s | split("/") | last)
        else s
        end;

    def format_owner(o):
        if $owner_format == "bare-name" then bare(o) else o end;

    [.[]
     | select(.kind == "Domain" or .kind == "System")
     | (.metadata.name | tostring) as $name
     | (if .kind == "System" then ($paths.systems[$name] // $name)
        else ($paths.domains[$name] // $name) end) as $key
     | (.spec.owner // "" | tostring) as $raw_owner
     | (if $raw_owner == "" then $default_owner else format_owner($raw_owner) end) as $owner
     | (.metadata.description // "" | tostring) as $raw_desc
     | (if $raw_desc == "" then $default_desc else $raw_desc end) as $desc
     | {key: $key, value:
         ({}
          + (if $desc != "" then {description: $desc} else {} end)
          + (if $owner != "" then {owner: $owner} else {} end))}
    ]
    | from_entries' "$ALL_ENTITIES")

COMPONENT_COUNT=$(echo "$COMPONENTS" | jq 'length')
DOMAIN_COUNT=$(echo "$DOMAINS" | jq 'length')

# When any structured filter is active, report how many annotated candidate
# components were dropped by include/exclude — gives operators visibility into
# what the filters removed rather than silently shrinking the catalog.
if [ -n "$INCLUDE_TYPES$EXCLUDE_TYPES$INCLUDE_LIFECYCLES$EXCLUDE_LIFECYCLES$INCLUDE_DOMAINS$EXCLUDE_DOMAINS$INCLUDE_SYSTEMS$EXCLUDE_SYSTEMS" ]; then
    CANDIDATE_COUNT=$(jq --arg annotation "$COMPONENT_ID_ANNOTATION" '
        [ .[]
          | select(.kind == "Component" or .kind == "API" or .kind == "Resource")
          | (((.metadata.annotations // {})[$annotation]) // "" | tostring)
          | select(length > 0) ] | length' "$ALL_ENTITIES")
    echo "Filters dropped $((CANDIDATE_COUNT - COMPONENT_COUNT)) of $CANDIDATE_COUNT candidate component(s)"
fi

# --- Verify the component repos exist ------------------------------------
# A Backstage catalog is a hand-maintained document, so the id annotation is a
# *claim* about a repo, not a fact: renamed, deleted and typo'd slugs are normal.
# Nothing downstream catches one — the hub's catalog merge does not validate repo
# existence, and the association job that would notice the 404 fails and retries
# to exhaustion — so each bad annotation leaves a component with no repo behind
# it: no collections, no checks, forever. Verify before writing instead.
#
# Deliberately fails OPEN. A transient GitHub error, a missing token, a
# host we can't address or a wholesale "nothing exists" answer all mean
# "we don't know", and the catalog must not shrink on "we don't know" —
# only on a specific repo GitHub positively reports as absent.
# Sets VERIFIED_COMPONENTS rather than echoing it, so the progress/warning
# logging below can't end up captured as part of the JSON payload.
verify_component_repos() {
    local components="$1"
    VERIFIED_COMPONENTS="$components"

    if [ "$VERIFY_REPOS" != "true" ]; then
        echo "verify_repos is off — writing components without checking their repos exist"
        return 0
    fi

    if [ -z "${LUNAR_SECRET_GH_TOKEN:-}" ]; then
        echo "WARNING: verify_repos is on but no GH_TOKEN secret is configured — components" >&2
        echo "  whose Backstage annotation names a non-existent repo will still be written." >&2
        echo "  Set the GH_TOKEN secret (Metadata: Read on the orgs in your catalog) to enable" >&2
        echo "  verification, or set verify_repos: \"false\" to silence this warning." >&2
        return 0
    fi

    # The id prefix is the SCM host, so a non-github.com prefix means the repos
    # live on GHES and github_api_url must point at it. Querying api.github.com
    # for GHES repos would report every one of them missing, so refuse to guess.
    local host="${COMPONENT_ID_PREFIX%/}"
    if [ "$host" != "github.com" ] && [ "$GITHUB_API_URL" = "https://api.github.com" ]; then
        echo "WARNING: component_id_prefix is '$COMPONENT_ID_PREFIX' but github_api_url is still" >&2
        echo "  the github.com default — skipping repo verification rather than checking the" >&2
        echo "  wrong host. Set github_api_url to your GitHub Enterprise API base (e.g." >&2
        echo "  https://$host/api/v3) to enable it." >&2
        return 0
    fi

    # GHES serves GraphQL at /api/graphql, not under the /api/v3 REST base.
    local graphql_url
    case "$GITHUB_API_URL" in
        */api/v3) graphql_url="${GITHUB_API_URL%/api/v3}/api/graphql" ;;
        *)        graphql_url="$GITHUB_API_URL/graphql" ;;
    esac

    # Distinct owner/repo pairs behind the component ids. Strip the id prefix,
    # then keep the first two path segments so monorepo-style
    # `<owner>/<repo>/<subdir>` ids resolve to their backing repo.
    local slugs_file present_file batch_file resp_file
    slugs_file=$(mktemp); present_file=$(mktemp)
    batch_file=$(mktemp); resp_file=$(mktemp)

    echo "$components" | jq -r --arg prefix "$COMPONENT_ID_PREFIX" '
        keys[]
        | ltrimstr($prefix)
        | split("/")
        | select(length >= 2 and .[0] != "" and .[1] != "")
        | .[0] + "/" + .[1]
    ' | sort -u > "$slugs_file"

    local slug_total
    slug_total=$(grep -c . "$slugs_file" || true)
    if [ "$slug_total" -eq 0 ]; then
        echo "No component id resolved to an <owner>/<repo> pair — skipping repo verification"
        rm -f "$slugs_file" "$present_file" "$batch_file" "$resp_file"
        return 0
    fi

    echo "Verifying $slug_total repo(s) exist via $graphql_url (batches of $VERIFY_BATCH_SIZE)"

    local offset=0 requests=0 hard_failure=0
    while [ "$offset" -lt "$slug_total" ]; do
        # Aliases are positional (r0, r1, ...) so the response maps back to the
        # slug we ASKED for. Keying off the returned nameWithOwner instead would
        # mis-drop a renamed repo, which resolves under its new name.
        jq -R -s -c --argjson off "$offset" --argjson n "$VERIFY_BATCH_SIZE" \
            'split("\n") | map(select(length > 0)) | .[$off:$off+$n]' \
            "$slugs_file" > "$batch_file"

        local query
        query=$(jq -r '
            to_entries
            | map("r\(.key): repository(owner: \(.value | split("/")[0] | @json), "
                  + "name: \(.value | split("/")[1] | @json)) { id }")
            | "query { " + join(" ") + " }"
        ' "$batch_file")

        local code
        code=$(jq -n --arg q "$query" '{query: $q}' | curl -sS -o "$resp_file" -w '%{http_code}' \
            -X POST \
            -H "Authorization: Bearer $LUNAR_SECRET_GH_TOKEN" \
            -H "Content-Type: application/json" \
            --data @- "$graphql_url" 2>/dev/null || echo "000")
        requests=$((requests + 1))

        if [ "$code" != "200" ]; then
            echo "WARNING: repo verification request failed (HTTP $code): $(head -c 200 "$resp_file" 2>/dev/null)" >&2
            hard_failure=1
            break
        fi

        # A missing repo comes back as `data.rN: null` plus a NOT_FOUND entry in
        # `errors` — a 200 with partial data, not an error response. Anything
        # that did resolve is present.
        #
        # `|| hard_failure=1` is load-bearing: a 200 carrying a non-JSON body (a
        # proxy or WAF error page, a truncated response) makes jq exit non-zero,
        # and under `set -e` that would kill the whole cataloger run — turning a
        # "we don't know" into a hard failure, the exact opposite of the
        # fail-open contract. Treat it as inconclusive instead.
        if ! jq -r --slurpfile batch "$batch_file" '
            (.data // {})
            | to_entries[]
            | select(.value != null)
            | $batch[0][(.key | ltrimstr("r") | tonumber)]
        ' "$resp_file" >> "$present_file" 2>/dev/null; then
            echo "WARNING: could not parse the GitHub GraphQL response (HTTP 200, body head: $(head -c 120 "$resp_file" 2>/dev/null))" >&2
            hard_failure=1
            break
        fi

        offset=$((offset + VERIFY_BATCH_SIZE))
    done

    local present_total
    present_total=$(sort -u "$present_file" | grep -c . || true)

    # "Nothing at all exists" is a misconfiguration (wrong host, unscoped or
    # expired token), not a catalog where every entry is stale. Don't act on it.
    if [ "$hard_failure" -eq 1 ] || [ "$present_total" -eq 0 ]; then
        echo "WARNING: repo verification is inconclusive ($present_total/$slug_total repos resolved" >&2
        echo "  over $requests request(s)) — writing all components unfiltered. Check that" >&2
        echo "  GH_TOKEN is valid and covers every org in the Backstage catalog." >&2
        rm -f "$slugs_file" "$present_file" "$batch_file" "$resp_file"
        return 0
    fi

    VERIFIED_COMPONENTS=$(echo "$components" | jq \
        --arg prefix "$COMPONENT_ID_PREFIX" \
        --rawfile present "$present_file" '
        ($present | split("\n") | map(select(length > 0))) as $ok
        | with_entries(
            (.key | ltrimstr($prefix) | split("/")) as $parts
            | select(
                ($parts | length) < 2 or $parts[0] == "" or $parts[1] == ""
                or (($parts[0] + "/" + $parts[1]) | IN($ok[]))
              )
          )')

    # Name every dropped component: the fix is in Backstage, so the operator
    # needs the ids, not just a count.
    local dropped_ids
    dropped_ids=$(jq -rn --argjson before "$components" --argjson after "$VERIFIED_COMPONENTS" \
        '($before | keys) - ($after | keys) | .[] | "  " + .')
    if [ -n "$dropped_ids" ]; then
        echo "Repo does not exist (or GH_TOKEN cannot see it) — skipping:"
        printf '%s\n' "$dropped_ids"
    fi
    echo "Repo verification: $present_total/$slug_total repo(s) exist, $requests GraphQL request(s)"

    rm -f "$slugs_file" "$present_file" "$batch_file" "$resp_file"
}

verify_component_repos "$COMPONENTS"
COMPONENTS="$VERIFIED_COMPONENTS"
VERIFIED_COUNT=$(echo "$COMPONENTS" | jq 'length')
if [ "$VERIFIED_COUNT" -ne "$COMPONENT_COUNT" ]; then
    echo "Repo verification dropped $((COMPONENT_COUNT - VERIFIED_COUNT)) of $COMPONENT_COUNT component(s)"
    COMPONENT_COUNT=$VERIFIED_COUNT
fi

echo "Components to write: $COMPONENT_COUNT"
echo "Domains to write:    $DOMAIN_COUNT"

# --- Write to Lunar catalog ----------------------------------------------
# Hub validateDomainRefs requires every component.domain to exist under
# catalog .domains, so write domains first.

if [ "$DOMAIN_COUNT" -gt 0 ]; then
    if echo "$DOMAINS" | lunar catalog raw --json '.domains' -; then
        echo "Wrote $DOMAIN_COUNT domains"
    else
        echo "Failed to write domains" >&2
        exit 1
    fi
fi

if [ "$COMPONENT_COUNT" -eq 0 ]; then
    echo ""
    echo "Backstage sync complete: 0 components, $DOMAIN_COUNT domains"
    exit 0
fi

WRITTEN=0
FAILED=0
if [ "$COMPONENT_COUNT" -le "$BATCH_SIZE" ]; then
    if echo "$COMPONENTS" | lunar catalog raw --json '.components' -; then
        WRITTEN=$COMPONENT_COUNT
    else
        FAILED=$COMPONENT_COUNT
    fi
else
    echo "$COMPONENTS" | jq 'to_entries' > "${ALL_ENTITIES}.entries"
    BATCH_NUM=0
    while true; do
        START=$((BATCH_NUM * BATCH_SIZE))
        if [ "$START" -ge "$COMPONENT_COUNT" ]; then break; fi
        END=$((START + BATCH_SIZE))
        if [ "$END" -gt "$COMPONENT_COUNT" ]; then END=$COMPONENT_COUNT; fi
        BATCH_NUM=$((BATCH_NUM + 1))
        COUNT=$((END - START))
        BATCH=$(jq --argjson s "$START" --argjson c "$COUNT" \
            '.[$s:$s+$c] | from_entries' "${ALL_ENTITIES}.entries")
        if echo "$BATCH" | lunar catalog raw --json '.components' -; then
            WRITTEN=$((WRITTEN + COUNT))
            echo "  batch $BATCH_NUM: wrote $COUNT components ($WRITTEN/$COMPONENT_COUNT)"
        else
            FAILED=$((FAILED + COUNT))
            echo "  batch $BATCH_NUM: FAILED ($COUNT components, continuing)" >&2
        fi
    done
fi

echo ""
echo "Backstage sync complete: $WRITTEN components written, $DOMAIN_COUNT domains written"
if [ "$FAILED" -gt 0 ]; then
    echo "  $FAILED components failed to write" >&2
    exit 1
fi