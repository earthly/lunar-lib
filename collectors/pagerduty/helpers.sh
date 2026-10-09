#!/bin/bash
# Shared by oncall.sh (the oncall and oncall-cron sub-collectors) and
# from-backstage-collector.sh (the from-backstage-collector sub-collector).
# The globals set here (READ_STATE, COMPONENT_JSON, ...) are read by those scripts.
# shellcheck disable=SC2034

# backstage_discovery switches the checked-out catalog-info.yaml on or off.
# The live catalog is the from-backstage-collector sub-collector's job, so it has no setting.
DISCOVERY="${LUNAR_VAR_BACKSTAGE_DISCOVERY:-false}"
case "$DISCOVERY" in
  true|false) ;;
  *) echo "backstage_discovery is '$DISCOVERY', but it takes \"true\" or \"false\"; not reading the catalog file. The from-backstage-collector sub-collector does the live lookup." >&2 ;;
esac
ANNOTATION_KEYS="${LUNAR_VAR_BACKSTAGE_ANNOTATIONS:-pagerduty.com/service-id,pagerduty/service-id}"

SERVICE_ID=""
DISCOVERED_VIA=""
SEARCHED=()
LOOKUP_ERRORS=()

require_api_key() {
  if [ -z "${LUNAR_SECRET_PAGERDUTY_API_KEY:-}" ]; then
    echo "PagerDuty collector requires PAGERDUTY_API_KEY secret." >&2
    exit 0
  fi
}

# The component's pagerduty/service-id meta, then the service_id input.
resolve_meta_and_input() {
  SEARCHED+=("meta:pagerduty/service-id")
  if [ -n "${LUNAR_COMPONENT_META:-}" ]; then
    SERVICE_ID="$(echo "$LUNAR_COMPONENT_META" | jq -r '."pagerduty/service-id" // empty' 2>/dev/null)" || SERVICE_ID=""
  fi
  if [ -n "$SERVICE_ID" ]; then
    DISCOVERED_VIA="meta:pagerduty/service-id"
    return 0
  fi
  SEARCHED+=("input:service_id")
  if [ -n "${LUNAR_VAR_SERVICE_ID:-}" ]; then
    SERVICE_ID="$LUNAR_VAR_SERVICE_ID"
    DISCOVERED_VIA="input:service_id"
  fi
}

# backstage_discovery: "true" — the annotations in the checked-out
# catalog-info.yaml. Either hook gives us the checkout: `oncall` runs on a code
# hook, which always clones, and `oncall-cron` sets clone-code: true.
resolve_from_checkout() {
  local paths p catalog_path="" catalog_json="" local_id=""
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
    for p in "${path_arr[@]}"; do
      p="$(echo "$p" | xargs)"
      [ -n "$p" ] && SEARCHED+=("file:$p (not found)")
    done
    return 0
  fi
  if ! catalog_json=$(yq ea -o=json '[.]' "./$catalog_path" 2>/dev/null); then
    echo "backstage_discovery: $catalog_path is not valid YAML" >&2
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

# read_component_json <budget-seconds> <pin-sha: true|false>
#
# Reads this component's JSON until the backstage collector's live lookup
# (.catalog.native.backstage.refs.entity) is in it, or the budget runs out.
# Sets COMPONENT_JSON, READ_STATE (ok | read_failed | no_lookup), WAITED and
# ATTEMPT.
#
# The from-backstage-collector sub-collector is dispatched off that path in the LIVE merged
# blob. Hub 4.9.0+ serves the --git-sha read below from that blob; older Hubs
# read a copy their mat workers drain asynchronously, so the first reads can
# come back without it. The other after-json collectors retry for 900s (codeql
# measured the lag at 195-292s+, and container-scan runs have resolved up to
# 530s after their record); this defaults to twice that, with a 60s backoff
# ceiling instead of 30s.
#
# --pr narrows to the PR. --git-sha pins the commit the wave fired for: without
# it, a default-branch read resolves the latest snapshot, which can be a later
# commit. The cron leg doesn't pin the sha: its head is the latest ingested
# commit, which may not have been collected yet.
read_component_json() {
  local budget="$1" pin_sha="$2" step backoff err
  local -a args=()
  step="${LUNAR_PAGERDUTY_TEST_BACKOFF_STEP:-5}"
  [ "$step" -ge 1 ] 2>/dev/null || step=5
  [ -n "${LUNAR_COMPONENT_PR:-}" ] && args+=(--pr "$LUNAR_COMPONENT_PR")
  if [ "$pin_sha" = true ] && [ -n "${LUNAR_COMPONENT_GIT_SHA:-}" ]; then
    args+=(--git-sha "$LUNAR_COMPONENT_GIT_SHA")
  fi
  err="${TMPDIR:-/tmp}/pagerduty-get-json.err"

  COMPONENT_JSON=""
  READ_STATE=read_failed
  ATTEMPT=0
  WAITED=0
  # LUNAR_COMPONENT_ID is injected by the Lunar runtime.
  # shellcheck disable=SC2153
  while :; do
    ATTEMPT=$((ATTEMPT + 1))
    if COMPONENT_JSON=$(lunar component get-json "$LUNAR_COMPONENT_ID" "${args[@]}" 2>"$err") \
       && [ -n "$COMPONENT_JSON" ]; then
      if printf '%s' "$COMPONENT_JSON" \
           | jq -e '.catalog.native.backstage.refs.entity | type == "object"' >/dev/null 2>&1; then
        READ_STATE=ok
        break
      fi
      READ_STATE=no_lookup
    else
      COMPONENT_JSON=""
      READ_STATE=read_failed
      # The CLI's own error, once, without cobra's usage block.
      if [ "$ATTEMPT" -eq 1 ] && [ -s "$err" ]; then
        sed -n '/^Usage:/q;p' "$err" | head -c 500 | sed 's/^/  get-json: /' >&2
      fi
    fi
    backoff=$((ATTEMPT * step))
    [ "$backoff" -gt $((step * 12)) ] && backoff=$((step * 12))
    [ $((WAITED + backoff)) -gt "$budget" ] && break
    sleep "$backoff"
    WAITED=$((WAITED + backoff))
  done
  if [ "$WAITED" -gt 0 ]; then
    echo "Waited ${WAITED}s across ${ATTEMPT} attempt(s) for the backstage collector's lookup to become readable." >&2
  fi
}

# resolve_from_backstage_json <component-json>
#
# The service ID from what the backstage collector read out of the live
# catalog: the component's own entity, then its System, then that System's
# Domain (a System catalog file: its own Domain). A lookup that couldn't
# complete ends the walk, because an earlier entity's ID would have won, and
# goes to LOOKUP_ERRORS.
resolve_from_backstage_json() {
  local state label id error
  while IFS=$'\x1f' read -r state label id error; do
    case "$state" in
      hit)
        SEARCHED+=("$label")
        if [ -n "$id" ]; then
          SERVICE_ID="$id"
          DISCOVERED_VIA="$label"
          return 0
        fi
        ;;
      miss)
        SEARCHED+=("$label (not in catalog)")
        ;;
      error)
        LOOKUP_ERRORS+=("$label: $error")
        echo "The backstage collector's lookup of $label failed ($error)." >&2
        return 0
        ;;
    esac
  done < <(printf '%s' "$1" | jq -r --arg keys "$ANNOTATION_KEYS" '
    ($keys | split(",") | map(gsub("^\\s+|\\s+$"; "")) | map(select(length > 0))) as $ks
    | def first_id($anns):
        [ $ks[] as $k | $anns[] | if type == "object" then .[$k] else null end
          | strings | gsub("\\s"; "") | select(. != "") ] | (.[0] // "");
      def canon($kind; $name; $ns):
        ($name | tostring | sub("^[A-Za-z]+:"; "")) as $n
        | if ($n | contains("/")) then "\($kind):\($n)" else "\($kind):\($ns)/\($n)" end;
      def ns_of($ref): (($ref // "") | capture("^[^:]+:(?<ns>[^/]+)/") | .ns) // null;
      def step($r; $label):
        if $r == null then empty
        elif ($r | has("error")) then {state: "error", label: $label, error: ($r.error | tostring)}
        elif $r.exists == false then {state: "miss", label: $label}
        elif $r.exists == true and ($r.ref | type) == "string"
          then {state: "hit", label: $r.ref, id: first_id([$r.annotations])}
        else {state: "error", label: $label, error: "the entity it returned could not be read"} end;
      .catalog.native.backstage as $b
      | ($b.metadata.namespace // "default") as $ns
      | ($b.refs // {}) as $refs
      | (($refs.entity.kind // $b.kind // "Component") | ascii_downcase) as $kind
      | ( step($refs.entity; canon($kind; $refs.entity.name // ""; $ns)),
          step($refs.system; canon("system"; $refs.system.name // ""; $ns)),
          step($refs.system_domain;
               canon("domain"; $refs.system_domain.name // ""; (ns_of($refs.system.ref) // $ns))),
          (if $kind == "system" then step($refs.domain; canon("domain"; $refs.domain.name // ""; $ns)) else empty end) )
      | [.state, .label, (.id // ""), (.error // "")] | join("\u001f")
  ' 2>/dev/null)
}

# file_id_from_backstage_json <component-json> — the service ID in the catalog
# file as the backstage collector parsed it: the first configured key with a
# value, across its Component entities.
file_id_from_backstage_json() {
  printf '%s' "$1" | jq -r --arg keys "$ANNOTATION_KEYS" '
    ($keys | split(",") | map(gsub("^\\s+|\\s+$"; "")) | map(select(length > 0))) as $ks
    | .catalog.native.backstage as $b
    | [ ($b.entities // [])[] | select(type == "object" and .kind == "Component") | .metadata.annotations ]
    | (if length > 0 then . else [ $b.metadata.annotations ] end) as $anns
    | [ $ks[] as $k | $anns[] | if type == "object" then .[$k] else null end
        | strings | gsub("\\s"; "") | select(. != "") ]
    | (.[0] // "")
  ' 2>/dev/null || :
}

# oncall_reads_backstage_file <component-json> — whether the catalog file the
# backstage collector parsed is one oncall reads from its checkout: a
# backstage_catalog_paths entry in the component's own directory. With
# search_parent_dirs the backstage collector can read a shared ancestor file
# (recorded as ../…), which oncall never sees.
oncall_reads_backstage_file() {
  local path p
  local -a paths=()
  path=$(printf '%s' "$1" | jq -r '.catalog.native.backstage.path | strings' 2>/dev/null) || path=""
  [ -n "$path" ] || return 1
  IFS=',' read -ra paths <<< "${LUNAR_VAR_BACKSTAGE_CATALOG_PATHS:-catalog-info.yaml,catalog-info.yml}"
  for p in "${paths[@]}"; do
    p="$(echo "$p" | xargs)"
    [ "${p#./}" = "$path" ] && return 0
  done
  return 1
}

# finish_unresolved [hint] — no service ID: write .oncall.service_lookup with
# the places looked, which tells the oncall policy this apart from a collector
# that never ran. A lookup that couldn't complete goes in its errors, so the
# policy skips instead of reporting a missing mapping during an outage.
# Sub-collectors each record what they searched, so .oncall.service_lookup can
# sit next to a .oncall.service another one found; the policy reads
# .oncall.service first.
finish_unresolved() {
  local looked_in="" searched errors
  if [ ${#SEARCHED[@]} -gt 0 ]; then
    looked_in="$(printf '%s, ' "${SEARCHED[@]}")"
    looked_in=" (looked in: ${looked_in%, })"
  fi
  echo "No PagerDuty service ID found${looked_in}." >&2
  if [ ${#LOOKUP_ERRORS[@]} -gt 0 ]; then
    echo "A Backstage lookup didn't complete, so this is recorded as an error, not a missing mapping." >&2
  elif [ -n "${1:-}" ]; then
    echo "$1" >&2
  fi
  searched=$(printf '%s\n' "${SEARCHED[@]}" | jq -R 'select(length > 0)' | jq -sc .)
  errors=$(printf '%s\n' "${LOOKUP_ERRORS[@]}" | jq -R 'select(length > 0)' | jq -sc .)
  jq -n '{"tool": "pagerduty", "integration": "api"}' | lunar collect -j ".oncall.source" -
  jq -n --argjson s "$searched" --argjson e "$errors" '
    (if ($s | length) > 0 then {searched: $s} else {} end)
    + (if ($e | length) > 0 then {errors: $e} else {} end)' \
    | lunar collect -j ".oncall.service_lookup" -
  exit 0
}

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

# Query PagerDuty for $SERVICE_ID and write .oncall.
collect_pagerduty() {
  echo "PagerDuty service ID '$SERVICE_ID' resolved via $DISCOVERED_VIA" >&2

  BASE_URL="${LUNAR_VAR_PAGERDUTY_BASE_URL:-https://api.pagerduty.com}"
  BASE_URL="${BASE_URL%/}"
  AUTH="Authorization: Token token=${LUNAR_SECRET_PAGERDUTY_API_KEY}"
  ACCEPT="Accept: application/vnd.pagerduty+json;version=2"

  # Always write source metadata.
  jq -n '{"tool": "pagerduty", "integration": "api"}' | lunar collect -j ".oncall.source" -

  # The ID goes into the request path, next to the API key. Only a plain
  # PagerDuty ID is sent, so an annotation can't point the key at another
  # endpoint. A value that isn't one is still recorded, with where it came from.
  if ! [[ "$SERVICE_ID" =~ ^[A-Za-z0-9]+$ ]]; then
    echo "'$SERVICE_ID' (via $DISCOVERED_VIA) is not a PagerDuty service ID; not querying PagerDuty." >&2
    jq -n --arg id "$SERVICE_ID" --arg via "$DISCOVERED_VIA" '{id: $id, discovered_via: $via}' \
      | lunar collect -j ".oncall.service" -
    return 0
  fi

  # Fetch service.
  local SERVICE_JSON
  SERVICE_JSON="$(pd_get "/services/${SERVICE_ID}")" || {
    echo "Unable to fetch PagerDuty service ${SERVICE_ID}." >&2
    # Still record the mapping, so a wrong or deleted ID is traceable to its source.
    jq -n --arg id "$SERVICE_ID" --arg via "$DISCOVERED_VIA" '{id: $id, discovered_via: $via}' \
      | lunar collect -j ".oncall.service" -
    return 0
  }

  local SERVICE_NAME SERVICE_STATUS ESCALATION_POLICY_ID
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
  local HAS_ESCALATION=false ESCALATION_LEVELS=0 ESCALATION_NAME="" EP_JSON sid
  local -a SCHEDULE_IDS=()

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
  local HAS_SCHEDULE=false PARTICIPANTS=0 ROTATION="unknown" SCHED_JSON ROTATION_SECS

  if [ ${#SCHEDULE_IDS[@]} -gt 0 ]; then
    if SCHED_JSON="$(pd_get "/schedules/${SCHEDULE_IDS[0]}")"; then
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
}
