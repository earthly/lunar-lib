#!/bin/bash
set -e

# Resolve the Datadog team: cataloger-set meta annotation first, then the input.
TEAM=""
if [ -n "${LUNAR_COMPONENT_META:-}" ]; then
  TEAM="$(echo "$LUNAR_COMPONENT_META" | jq -r '."datadog/team" // empty')"
fi
if [ -z "$TEAM" ] && [ -n "${LUNAR_VAR_TEAM:-}" ]; then
  TEAM="$LUNAR_VAR_TEAM"
fi

if [ -z "$TEAM" ]; then
  echo "No Datadog team found. Set 'datadog/team' meta or the team input to collect On-Call data." >&2
  exit 0
fi

if [ -z "${LUNAR_SECRET_DATADOG_API_KEY:-}" ] || [ -z "${LUNAR_SECRET_DATADOG_APP_KEY:-}" ]; then
  echo "Datadog On-Call collection requires DATADOG_API_KEY and DATADOG_APP_KEY secrets." >&2
  exit 0
fi

SITE="${LUNAR_VAR_DATADOG_SITE:-${DATADOG_SITE:-datadoghq.com}}"
API_BASE="https://api.${SITE}"
ONCALL_SCOPE="The application key needs the on_call_read scope."
TEAMS_SCOPE="The application key needs the teams_read scope (or set the team ID instead of its handle)."

# A fresh directory per run: dev runs and tests reuse one filesystem.
WORK="$(mktemp -d)"
TEAM_FILE="$WORK/team.json"
PAGE_FILE="$WORK/teams-page.json"
RULES_FILE="$WORK/routing-rules.json"
POLICY_FILE="$WORK/escalation-policy.json"
SCHEDULE_FILE="$WORK/schedule.json"

uri() { jq -rn --arg v "$1" '$v | @uri'; }

# fetch <path> <file> <scope-hint> — GET a Datadog API path into <file>.
# Returns 0 on 2xx and 2 on 404. Anything else exits the script non-zero, so a
# rate limit, an outage or a missing scope never records a false "no on-call".
# curl retries 429, 5xx and connection failures itself; 401/403/404 are final.
fetch() {
  local path="$1" out="$2" hint="$3" code rc
  set +e
  code="$(curl -sS \
    --retry 3 --retry-delay 2 --retry-max-time 60 --retry-connrefused \
    --max-time 30 \
    -o "$out" -w '%{http_code}' \
    -H "DD-API-KEY: ${LUNAR_SECRET_DATADOG_API_KEY}" \
    -H "DD-APPLICATION-KEY: ${LUNAR_SECRET_DATADOG_APP_KEY}" \
    "${API_BASE}${path}")"
  rc=$?
  set -e
  if [ "$rc" -ne 0 ]; then
    echo "Datadog request to ${path} failed after retries (curl exit ${rc})." >&2
    exit 1
  fi
  case "$code" in
    2??)
      if ! jq -e 'type == "object"' "$out" >/dev/null 2>&1; then
        echo "Datadog request to ${path} returned HTTP ${code} without a JSON object body." >&2
        exit 1
      fi
      return 0
      ;;
    404) return 2 ;;
    401|403)
      echo "Datadog request to ${path} returned HTTP ${code}. ${hint}" >&2
      exit 1
      ;;
    *)
      echo "Datadog request to ${path} returned HTTP ${code}." >&2
      exit 1
      ;;
  esac
}

# A team ID is used as-is. A handle is resolved through the Teams API, whose
# keyword filter also matches team names and member emails, so match exactly.
UUID_RE='^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
TEAM_ID=""
TEAM_NAME=""
if [[ "$TEAM" =~ $UUID_RE ]]; then
  TEAM_ID="$TEAM"
else
  KEYWORD="$(uri "$TEAM")"
  page=0
  while [ "$page" -lt 10 ]; do
    if ! fetch "/api/v2/team?filter%5Bkeyword%5D=${KEYWORD}&page%5Bsize%5D=100&page%5Bnumber%5D=${page}" "$PAGE_FILE" "$TEAMS_SCOPE"; then
      echo "Datadog Teams API returned HTTP 404." >&2
      exit 1
    fi
    jq --arg h "$TEAM" 'first(.data[]? | select(.attributes.handle == $h)) // empty' "$PAGE_FILE" > "$TEAM_FILE"
    if [ -s "$TEAM_FILE" ]; then
      TEAM_ID="$(jq -r '.id // empty' "$TEAM_FILE")"
      TEAM_NAME="$(jq -r '.attributes.name // empty' "$TEAM_FILE")"
      break
    fi
    if [ "$(jq '.data | length' "$PAGE_FILE")" -lt 100 ]; then
      break
    fi
    page=$((page + 1))
  done
  if [ -z "$TEAM_ID" ]; then
    echo "No Datadog team has the handle '${TEAM}'." >&2
    exit 1
  fi
fi

# Routing rules run top to bottom and the first match routes the page, so the
# rule that represents the team is the fallback: no query and no time
# restriction, which Datadog requires last. Grade the policy it pages; if it
# pages none, take the first rule before it that does. Rules after the
# fallback never match. A rule names its policy through either its policy
# relationship or an escalation_policy action.
POLICY_ID=""
HAVE_RULES=false
if fetch "/api/v2/on-call/teams/$(uri "$TEAM_ID")/routing-rules?include=rules" "$RULES_FILE" "$ONCALL_SCOPE"; then
  HAVE_RULES=true
  POLICY_ID="$(jq -r '
    (.included // []) as $inc
    | [(.data.relationships.rules.data // [])[].id] as $order
    | (if ($order | length) > 0
       then [$order[] as $id | first($inc[] | select(.type == "team_routing_rules" and .id == $id))]
       else [$inc[] | select(.type == "team_routing_rules")] end)
    | map({
        fallback: ((.attributes.query // "") == "" and .attributes.time_restriction == null),
        policy: ([(.relationships.policy.data.id // empty),
                  ((.attributes.actions // [])[] | select(.type == "escalation_policy") | .policy_id // empty)]
                 | map(select(. != "")) | .[0] // "")
      })
    | ((to_entries | map(select(.value.fallback)) | .[0].key) // (length - 1)) as $end
    | .[0:($end + 1)]
    | ((map(select(.fallback and .policy != "")) | .[0].policy)
       // (map(select(.policy != "")) | .[0].policy)
       // empty)
  ' "$RULES_FILE")"
  if [ -z "$POLICY_ID" ]; then
    echo "No routing rule of team ${TEAM_ID} pages an escalation policy." >&2
  fi
else
  echo "Datadog has no On-Call routing rules for team ${TEAM_ID}." >&2
fi

# Escalation policy: its steps are the levels, and the first schedule a step
# targets, in step order, is the rotation. A schedule_target pages a schedule
# at a configured position; its included object names the schedule.
ESCALATION_EXISTS=false
LEVELS=0
POLICY_NAME=""
SCHEDULE_ID=""
if [ -n "$POLICY_ID" ]; then
  if fetch "/api/v2/on-call/escalation-policies/$(uri "$POLICY_ID")?include=teams,steps,steps.targets" "$POLICY_FILE" "$ONCALL_SCOPE"; then
    ESCALATION_EXISTS=true
    LEVELS="$(jq '(.data.relationships.steps.data // []) | length' "$POLICY_FILE")"
    POLICY_NAME="$(jq -r '.data.attributes.name // empty' "$POLICY_FILE")"
    SCHEDULE_ID="$(jq -r '
      (.included // []) as $inc
      | [(.data.relationships.steps.data // [])[].id as $sid
         | first($inc[] | select(.type == "steps" and .id == $sid))
         | (.relationships.targets.data // [])[]
         | if .type == "schedules" then .id
           elif .type == "schedule_target" then
             (.id as $tid
              | first($inc[] | select(.type == "schedule_target" and .id == $tid))
              | .relationships.schedule.data.id // empty)
           else empty end]
      | .[0] // empty
    ' "$POLICY_FILE")"
    if [ -z "$TEAM_NAME" ]; then
      TEAM_NAME="$(jq -r --arg t "$TEAM_ID" 'first(.included[]? | select(.type == "teams" and .id == $t) | .attributes.name) // empty' "$POLICY_FILE")"
    fi
  else
    echo "Escalation policy ${POLICY_ID}, named by the team's routing rules, was not found." >&2
  fi
fi

# Schedule: participants are the distinct users across the layers that have
# not ended, leaving out users Datadog reports as deactivated (a user with no
# status still counts). The first such layer's interval gives the rotation.
SCHEDULE_EXISTS=false
PARTICIPANTS=0
ROTATION="unknown"
SCHEDULE_NAME=""
if [ -n "$SCHEDULE_ID" ]; then
  if fetch "/api/v2/on-call/schedules/$(uri "$SCHEDULE_ID")?include=teams,layers,layers.members,layers.members.user" "$SCHEDULE_FILE" "$ONCALL_SCOPE"; then
    SCHEDULE_EXISTS=true
    SCHEDULE_NAME="$(jq -r '.data.attributes.name // empty' "$SCHEDULE_FILE")"
    jq '
      (.included // []) as $inc
      | (now | todate) as $now
      | [(.data.relationships.layers.data // [])[].id as $lid
         | first($inc[] | select(.type == "layers" and .id == $lid))
         | select((.attributes.end_date // "") == "" or .attributes.end_date > $now)] as $layers
      | ([$inc[] | select(.type == "users") | {key: .id, value: (.attributes.status // "")}] | from_entries) as $status
      | {
          participants: ([$layers[] | (.relationships.members.data // [])[].id as $mid
                          | (first($inc[] | select(.type == "members" and .id == $mid)) | .relationships.user.data.id) // empty]
                         | unique | map(select($status[.] != "deactivated")) | length),
          rotation_seconds: (($layers[0].attributes.interval.days // 0) * 86400
                             + ($layers[0].attributes.interval.seconds // 0))
        }
    ' "$SCHEDULE_FILE" > "$WORK/schedule-summary.json"
    PARTICIPANTS="$(jq '.participants' "$WORK/schedule-summary.json")"
    ROTATION_SECS="$(jq '.rotation_seconds' "$WORK/schedule-summary.json")"
    if [ "$ROTATION_SECS" -le 0 ]; then
      ROTATION="unknown"
    elif [ "$ROTATION_SECS" -le 86400 ]; then
      ROTATION="daily"
    elif [ "$ROTATION_SECS" -le 604800 ]; then
      ROTATION="weekly"
    else
      ROTATION="custom"
    fi
    if [ -z "$TEAM_NAME" ]; then
      TEAM_NAME="$(jq -r --arg t "$TEAM_ID" 'first(.included[]? | select(.type == "teams" and .id == $t) | .attributes.name) // empty' "$SCHEDULE_FILE")"
    fi
  else
    echo "Schedule ${SCHEDULE_ID}, targeted by the escalation policy, was not found." >&2
  fi
fi

# Every request either succeeded or returned a definitive 404: write the result.
jq -n \
  --arg team_id "$TEAM_ID" \
  --arg team_name "$TEAM_NAME" \
  --argjson esc_exists "$ESCALATION_EXISTS" \
  --argjson levels "$LEVELS" \
  --arg policy_id "$POLICY_ID" \
  --arg policy_name "$POLICY_NAME" \
  --argjson sched_exists "$SCHEDULE_EXISTS" \
  --argjson participants "$PARTICIPANTS" \
  --arg rotation "$ROTATION" \
  --arg schedule_id "$SCHEDULE_ID" \
  --arg schedule_name "$SCHEDULE_NAME" \
  '{
    service: {id: $team_id, name: $team_name},
    escalation: ({exists: $esc_exists, levels: $levels, policy_name: $policy_name}
                 + (if $esc_exists then {id: $policy_id} else {} end)),
    schedule: ({exists: $sched_exists, participants: $participants, rotation: $rotation}
               + (if $sched_exists then {id: $schedule_id, name: $schedule_name} else {} end)),
    summary: {has_oncall: $sched_exists, has_escalation: $esc_exists, min_participants: $participants}
  }' | lunar collect -j ".oncall" -

if [ -s "$TEAM_FILE" ]; then
  lunar collect -j ".oncall.native.datadog.team" - < "$TEAM_FILE"
fi
if [ "$HAVE_RULES" = true ]; then
  lunar collect -j ".oncall.native.datadog.routing_rules" - < "$RULES_FILE"
fi
if [ "$ESCALATION_EXISTS" = true ]; then
  lunar collect -j ".oncall.native.datadog.escalation_policy" - < "$POLICY_FILE"
fi
if [ "$SCHEDULE_EXISTS" = true ]; then
  lunar collect -j ".oncall.native.datadog.schedule" - < "$SCHEDULE_FILE"
fi

jq -n '{"tool": "datadog", "integration": "api"}' | lunar collect -j ".oncall.source" -
