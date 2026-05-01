#!/bin/bash
set -e

# Resolve team_id: cataloger-set meta annotation first, then explicit input.
TEAM_ID=""
if [ -n "${LUNAR_COMPONENT_META:-}" ]; then
  TEAM_ID="$(echo "$LUNAR_COMPONENT_META" | jq -r '."opsgenie/team-id" // empty')"
fi

if [ -z "$TEAM_ID" ] && [ -n "${LUNAR_VAR_TEAM_ID:-}" ]; then
  TEAM_ID="$LUNAR_VAR_TEAM_ID"
fi

if [ -z "$TEAM_ID" ]; then
  echo "No OpsGenie team ID found. Set 'opsgenie/team-id' meta or the team_id input." >&2
  exit 0
fi

if [ -z "${LUNAR_SECRET_OPSGENIE_API_KEY:-}" ]; then
  echo "OpsGenie collector requires OPSGENIE_API_KEY secret." >&2
  exit 0
fi

BASE_URL="${LUNAR_VAR_OPSGENIE_BASE_URL:-https://api.opsgenie.com}"
BASE_URL="${BASE_URL%/}"
AUTH="Authorization: GenieKey ${LUNAR_SECRET_OPSGENIE_API_KEY}"

og_get() {
  local path="$1"
  set +e
  local response
  response="$(curl -fsS -H "$AUTH" "${BASE_URL}${path}")"
  local status=$?
  set -e
  if [ $status -ne 0 ] || [ -z "$response" ]; then
    return 1
  fi
  echo "$response"
}

# Always write source metadata.
jq -n '{"tool": "opsgenie", "integration": "api"}' | lunar collect -j ".oncall.source" -

# Fetch team.
TEAM_JSON="$(og_get "/v2/teams/${TEAM_ID}")" || {
  echo "Unable to fetch OpsGenie team ${TEAM_ID}." >&2
  exit 0
}

TEAM_NAME="$(echo "$TEAM_JSON" | jq -r '.data.name // empty')"

jq -n \
  --arg id "$TEAM_ID" \
  --arg name "$TEAM_NAME" \
  --arg status "active" \
  '{id: $id, name: $name, status: $status}' \
  | lunar collect -j ".oncall.service" -

echo "$TEAM_JSON" | lunar collect -j ".oncall.native.opsgenie.team" -

# Schedule — find first schedule owned by this team, then fetch its rotations
# for participant count.
HAS_SCHEDULE=false
PARTICIPANTS=0
ROTATION="unknown"

if SCHEDULES_JSON="$(og_get "/v2/schedules")"; then
  SCHEDULE_OBJ="$(echo "$SCHEDULES_JSON" | jq --arg tid "$TEAM_ID" '[.data[] | select(.ownerTeam.id == $tid)] | .[0] // empty')"
  if [ -n "$SCHEDULE_OBJ" ]; then
    SCHEDULE_ID="$(echo "$SCHEDULE_OBJ" | jq -r '.id // empty')"
    echo "$SCHEDULE_OBJ" | lunar collect -j ".oncall.native.opsgenie.schedule" -
    if [ -n "$SCHEDULE_ID" ] && ROTATIONS_JSON="$(og_get "/v2/schedules/${SCHEDULE_ID}/rotations")"; then
      HAS_SCHEDULE=true
      PARTICIPANTS="$(echo "$ROTATIONS_JSON" | jq '[.data[]?.participants[]? | select(.type == "user") | .id] | unique | length')"
      ROT_TYPE="$(echo "$ROTATIONS_JSON" | jq -r '.data[0].type // empty')"
      case "$ROT_TYPE" in
        weekly) ROTATION="weekly" ;;
        daily) ROTATION="daily" ;;
        hourly) ROTATION="custom" ;;
        *) ROTATION="unknown" ;;
      esac
      echo "$ROTATIONS_JSON" | lunar collect -j ".oncall.native.opsgenie.rotations" -
    fi
  fi
fi

jq -n \
  --argjson exists "$HAS_SCHEDULE" \
  --argjson participants "$PARTICIPANTS" \
  --arg rotation "$ROTATION" \
  '{exists: $exists, participants: $participants, rotation: $rotation}' \
  | lunar collect -j ".oncall.schedule" -

# Escalation — find first escalation policy owned by this team.
HAS_ESCALATION=false
ESCALATION_LEVELS=0
ESCALATION_NAME=""

if ESCALATIONS_JSON="$(og_get "/v2/escalations")"; then
  ESC_OBJ="$(echo "$ESCALATIONS_JSON" | jq --arg tid "$TEAM_ID" '[.data[] | select(.ownerTeam.id == $tid)] | .[0] // empty')"
  if [ -n "$ESC_OBJ" ]; then
    HAS_ESCALATION=true
    ESCALATION_LEVELS="$(echo "$ESC_OBJ" | jq '.rules | length')"
    ESCALATION_NAME="$(echo "$ESC_OBJ" | jq -r '.name // empty')"
    echo "$ESC_OBJ" | lunar collect -j ".oncall.native.opsgenie.escalation" -
  fi
fi

jq -n \
  --argjson exists "$HAS_ESCALATION" \
  --argjson levels "$ESCALATION_LEVELS" \
  --arg policy_name "$ESCALATION_NAME" \
  '{exists: $exists, levels: $levels, policy_name: $policy_name}' \
  | lunar collect -j ".oncall.escalation" -

# Summary.
jq -n \
  --argjson has_oncall "$HAS_SCHEDULE" \
  --argjson has_escalation "$HAS_ESCALATION" \
  --argjson min_participants "$PARTICIPANTS" \
  '{has_oncall: $has_oncall, has_escalation: $has_escalation, min_participants: $min_participants}' \
  | lunar collect -j ".oncall.summary" -
