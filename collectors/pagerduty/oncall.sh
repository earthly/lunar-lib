#!/bin/bash
set -e

# shellcheck source=collectors/pagerduty/backstage.sh disable=SC1091
source "$(dirname "$0")/backstage.sh"

if [ -z "${LUNAR_SECRET_PAGERDUTY_API_KEY:-}" ]; then
  echo "PagerDuty collector requires PAGERDUTY_API_KEY secret." >&2
  exit 0
fi

# ---------------------------------------------------------------------------
# discover_service_id implements backstage_discovery. With backstage_url set it
# looks the repo's Component up in the live catalog — the first `kind:
# Component` in its catalog-info.yaml, by name and namespace — and walks to its
# System and Domain (backstage.sh). Then it falls back to the annotations in
# the checked-out file itself. Either hook gives us the checkout: `oncall` runs
# on a code hook, which always clones, and `oncall-cron` sets clone-code: true.
#
# Sets SERVICE_ID / DISCOVERED_VIA on a hit, LOOKUP_ERROR when the live lookup
# couldn't complete, and appends every place it looked to SEARCHED. Never fails
# the collector.
# ---------------------------------------------------------------------------
discover_service_id() {
  local paths p catalog_path="" catalog_json="" comp="" comp_name="" comp_ns="" local_id=""
  local -a path_arr=()

  paths="${LUNAR_VAR_BACKSTAGE_CATALOG_PATHS:-catalog-info.yaml,catalog-info.yml}"
  IFS=',' read -ra path_arr <<< "$paths"
  for p in "${path_arr[@]}"; do
    p="$(echo "$p" | xargs)"
    [ -z "$p" ] && continue
    if [ -f "./$p" ]; then
      catalog_path="$p"
      break
    fi
  done

  if [ -z "$catalog_path" ]; then
    echo "backstage_discovery: no catalog file at '$paths' in the checkout" >&2
  elif catalog_json=$(yq ea -o=json '[.]' "./$catalog_path" 2>/dev/null); then
    echo "backstage_discovery: read $catalog_path" >&2
  else
    echo "backstage_discovery: $catalog_path is not valid YAML" >&2
    catalog_json=""
  fi

  if [ -n "$BACKSTAGE_BASE_URL" ]; then
    if [ -n "$catalog_json" ]; then
      comp=$(printf '%s' "$catalog_json" \
        | jq -c '[.[] | select(type == "object" and .kind == "Component")][0] // empty' 2>/dev/null) || comp=""
    fi
    if [ -n "$comp" ]; then
      comp_name=$(printf '%s' "$comp" | jq -r '.metadata.name | strings' 2>/dev/null) || comp_name=""
      comp_ns=$(printf '%s' "$comp" | jq -r '.metadata.namespace | strings' 2>/dev/null) || comp_ns=""
    fi
    if [ -n "$comp_name" ]; then
      backstage_live_lookup "${comp_ns:-default}" "$comp_name"
      if [ -n "$LIVE_ID" ]; then
        SERVICE_ID="$LIVE_ID"
        DISCOVERED_VIA="$LIVE_VIA"
        return 0
      fi
      LOOKUP_ERROR="$LIVE_ERROR"
    else
      echo "backstage_discovery: no Component in the catalog file to look up in Backstage" >&2
    fi
  fi

  if [ -z "$catalog_path" ]; then
    for p in "${path_arr[@]}"; do
      p="$(echo "$p" | xargs)"
      [ -n "$p" ] && SEARCHED+=("file:$p (not found)")
    done
    return 0
  fi
  if [ -z "$catalog_json" ]; then
    SEARCHED+=("file:$catalog_path (unparseable)")
    return 0
  fi

  # First non-empty value for the configured keys (tried in order) across all
  # the file's Component entities.
  local_id=$(printf '%s' "$catalog_json" | jq -r --arg keys "$ANNOTATION_KEYS" '
    ($keys | split(",") | map(gsub("^\\s+|\\s+$"; "")) | map(select(length > 0))) as $ks
    | [ .[] | select(type == "object" and .kind == "Component")
        | (.metadata | if type == "object" then .annotations else null end)
        | if type == "object" then . else {} end ] as $anns
    | [ $ks[] as $k | $anns[] | .[$k] // "" | tostring | gsub("\\s"; "") | select(. != "") ]
    | (.[0] // "")
  ' 2>/dev/null) || local_id=""
  SEARCHED+=("file:$catalog_path")
  if [ -n "$local_id" ]; then
    SERVICE_ID="$local_id"
    DISCOVERED_VIA="file:$catalog_path"
  fi
}

# Resolve the service ID: component meta, then the explicit input, then
# backstage_discovery (live catalog, then the checked-out catalog-info.yaml).
SERVICE_ID=""
DISCOVERED_VIA=""
LOOKUP_ERROR=""
SEARCHED=("meta:pagerduty/service-id")
if [ -n "${LUNAR_COMPONENT_META:-}" ]; then
  SERVICE_ID="$(echo "$LUNAR_COMPONENT_META" | jq -r '."pagerduty/service-id" // empty')"
fi
if [ -n "$SERVICE_ID" ]; then
  DISCOVERED_VIA="meta:pagerduty/service-id"
else
  SEARCHED+=("input:service_id")
  if [ -n "${LUNAR_VAR_SERVICE_ID:-}" ]; then
    SERVICE_ID="$LUNAR_VAR_SERVICE_ID"
    DISCOVERED_VIA="input:service_id"
  fi
fi

if [ -z "$SERVICE_ID" ] && [ "${LUNAR_VAR_BACKSTAGE_DISCOVERY:-false}" = "true" ]; then
  discover_service_id
fi

if [ -z "$SERVICE_ID" ]; then
  if [ -n "$LOOKUP_ERROR" ]; then
    # Nothing written: the mapping may exist on an entity we couldn't read, and
    # an outage must not read as "no service mapped".
    echo "No PagerDuty service ID found, and the live Backstage lookup failed ($LOOKUP_ERROR). Writing nothing." >&2
    exit 0
  fi
  # Every source answered and none maps the component. .oncall.unmapped tells
  # the oncall policy this apart from a collector that never ran.
  echo "No PagerDuty service ID found (looked in: $(printf '%s; ' "${SEARCHED[@]}")). Set 'pagerduty/service-id' meta, the service_id input, or enable backstage_discovery." >&2
  jq -n '{"tool": "pagerduty", "integration": "api"}' | lunar collect -j ".oncall.source" -
  printf '%s\n' "${SEARCHED[@]}" | jq -nR '{searched: [inputs]}' | lunar collect -j ".oncall.unmapped" -
  exit 0
fi
echo "PagerDuty service ID '$SERVICE_ID' resolved via $DISCOVERED_VIA" >&2

BASE_URL="${LUNAR_VAR_PAGERDUTY_BASE_URL:-https://api.pagerduty.com}"
BASE_URL="${BASE_URL%/}"
AUTH="Authorization: Token token=${LUNAR_SECRET_PAGERDUTY_API_KEY}"
ACCEPT="Accept: application/vnd.pagerduty+json;version=2"

# pd_get <path> — GET a PagerDuty API path. Echoes the response body on stdout
# and returns 0 on success; returns 1 on any failure.
#
# curl retries the transient failures itself — connection refused, timeouts,
# 429 and 5xx — with backoff between attempts, and honors a Retry-After header
# when PagerDuty sends one (its usual response when a burst of requests trips
# the account-wide rate limit). --retry-all-errors is deliberately NOT used: a
# 401/403/404 is a definitive answer we don't want to sit and retry. This
# mirrors the jira collector's jira_validate_ticket.
#
# The response code is captured separately so a failure can name the HTTP
# status (a 429 rate-limit reads very differently from a 403 bad-token or a
# 404 wrong-service-id when someone is debugging a flaky check).
#
# NOTE: a transient failure that outlives every retry still surfaces here as a
# plain `return 1`, exactly as before — the caller decides what that means.
# Stopping the caller from recording a bogus `exists:false` on such a failure
# is a separate, larger change (see the PR description); it is intentionally
# out of scope here.
pd_get() {
  local path="$1"
  local body_file http_code status response
  body_file="$(mktemp)"
  set +e
  http_code="$(curl -sS \
    --retry 3 \
    --retry-delay 2 \
    --retry-max-time 60 \
    --retry-connrefused \
    --max-time 30 \
    -o "$body_file" \
    -w '%{http_code}' \
    -H "$AUTH" -H "$ACCEPT" \
    "${BASE_URL}${path}")"
  status=$?
  set -e
  response="$(cat "$body_file")"
  rm -f "$body_file"

  if [ "$status" -ne 0 ]; then
    echo "PagerDuty request to ${path} failed after retries (curl exit ${status})." >&2
    return 1
  fi
  case "$http_code" in
    2??)
      if [ -z "$response" ]; then
        echo "PagerDuty request to ${path} returned an empty body (HTTP ${http_code})." >&2
        return 1
      fi
      echo "$response"
      ;;
    *)
      echo "PagerDuty request to ${path} returned HTTP ${http_code}." >&2
      return 1
      ;;
  esac
}

# Always write source metadata.
jq -n '{"tool": "pagerduty", "integration": "api"}' | lunar collect -j ".oncall.source" -

# The ID goes into the request path, next to the API key. Only a plain
# PagerDuty ID is sent, so an annotation can't point the key at another
# endpoint. A value that isn't one is still recorded, with where it came from.
if ! [[ "$SERVICE_ID" =~ ^[A-Za-z0-9]+$ ]]; then
  echo "'$SERVICE_ID' (via $DISCOVERED_VIA) is not a PagerDuty service ID; not querying PagerDuty." >&2
  jq -n --arg id "$SERVICE_ID" --arg via "$DISCOVERED_VIA" '{id: $id, discovered_via: $via}' \
    | lunar collect -j ".oncall.service" -
  exit 0
fi

# Fetch service.
SERVICE_JSON="$(pd_get "/services/${SERVICE_ID}")" || {
  echo "Unable to fetch PagerDuty service ${SERVICE_ID}." >&2
  # Still record the mapping, so a wrong or deleted ID is traceable to its source.
  jq -n --arg id "$SERVICE_ID" --arg via "$DISCOVERED_VIA" '{id: $id, discovered_via: $via}' \
    | lunar collect -j ".oncall.service" -
  exit 0
}

SERVICE_NAME="$(echo "$SERVICE_JSON" | jq -r '.service.name // empty')"
SERVICE_STATUS="$(echo "$SERVICE_JSON" | jq -r '.service.status // empty')"
ESCALATION_POLICY_ID="$(echo "$SERVICE_JSON" | jq -r '.service.escalation_policy.id // empty')"

jq -n \
  --arg id "$SERVICE_ID" \
  --arg name "$SERVICE_NAME" \
  --arg status "$SERVICE_STATUS" \
  --arg via "$DISCOVERED_VIA" \
  '{id: $id, name: $name, status: $status, discovered_via: $via}' \
  | lunar collect -j ".oncall.service" -

# Stash the raw service response.
echo "$SERVICE_JSON" | lunar collect -j ".oncall.native.pagerduty.service" -

# Escalation policy.
HAS_ESCALATION=false
ESCALATION_LEVELS=0
ESCALATION_NAME=""
SCHEDULE_IDS=()

if [ -n "$ESCALATION_POLICY_ID" ]; then
  if EP_JSON="$(pd_get "/escalation_policies/${ESCALATION_POLICY_ID}")"; then
    HAS_ESCALATION=true
    ESCALATION_LEVELS="$(echo "$EP_JSON" | jq '.escalation_policy.escalation_rules | length')"
    ESCALATION_NAME="$(echo "$EP_JSON" | jq -r '.escalation_policy.name // empty')"
    echo "$EP_JSON" | lunar collect -j ".oncall.native.pagerduty.escalation_policy" -
    while IFS= read -r sid; do
      [ -n "$sid" ] && SCHEDULE_IDS+=("$sid")
    done < <(echo "$EP_JSON" | jq -r '[.escalation_policy.escalation_rules[].targets[] | select(.type == "schedule_reference") | .id] | unique | .[]')
  fi
fi

jq -n \
  --argjson exists "$HAS_ESCALATION" \
  --argjson levels "$ESCALATION_LEVELS" \
  --arg policy_name "$ESCALATION_NAME" \
  '{exists: $exists, levels: $levels, policy_name: $policy_name}' \
  | lunar collect -j ".oncall.escalation" -

# Schedule — take the first schedule referenced by the escalation policy.
HAS_SCHEDULE=false
PARTICIPANTS=0
ROTATION="unknown"

if [ ${#SCHEDULE_IDS[@]} -gt 0 ]; then
  FIRST_SCHEDULE_ID="${SCHEDULE_IDS[0]}"
  if SCHED_JSON="$(pd_get "/schedules/${FIRST_SCHEDULE_ID}")"; then
    HAS_SCHEDULE=true
    PARTICIPANTS="$(echo "$SCHED_JSON" | jq '[.schedule.schedule_layers[].users[].user.id] | unique | length')"
    ROTATION_SECS="$(echo "$SCHED_JSON" | jq '.schedule.schedule_layers[0].rotation_turn_length_seconds // 0')"
    if [ "$ROTATION_SECS" -le 0 ]; then
      ROTATION="unknown"
    elif [ "$ROTATION_SECS" -le 86400 ]; then
      ROTATION="daily"
    elif [ "$ROTATION_SECS" -le 604800 ]; then
      ROTATION="weekly"
    else
      ROTATION="custom"
    fi
    echo "$SCHED_JSON" | lunar collect -j ".oncall.native.pagerduty.schedule" -
  fi
fi

jq -n \
  --argjson exists "$HAS_SCHEDULE" \
  --argjson participants "$PARTICIPANTS" \
  --arg rotation "$ROTATION" \
  '{exists: $exists, participants: $participants, rotation: $rotation}' \
  | lunar collect -j ".oncall.schedule" -

# Summary.
jq -n \
  --argjson has_oncall "$HAS_SCHEDULE" \
  --argjson has_escalation "$HAS_ESCALATION" \
  --argjson min_participants "$PARTICIPANTS" \
  '{has_oncall: $has_oncall, has_escalation: $has_escalation, min_participants: $min_participants}' \
  | lunar collect -j ".oncall.summary" -
