#!/bin/bash
set -e

# Resolve service_id: cataloger-set meta annotation first, then explicit input.
SERVICE_ID=""
if [ -n "${LUNAR_COMPONENT_META:-}" ]; then
  SERVICE_ID="$(echo "$LUNAR_COMPONENT_META" | jq -r '."pagerduty/service-id" // empty')"
fi

if [ -z "$SERVICE_ID" ] && [ -n "${LUNAR_VAR_SERVICE_ID:-}" ]; then
  SERVICE_ID="$LUNAR_VAR_SERVICE_ID"
fi

if [ -z "$SERVICE_ID" ]; then
  echo "No PagerDuty service ID found. Set 'pagerduty/service-id' meta or the service_id input." >&2
  exit 0
fi

if [ -z "${LUNAR_SECRET_PAGERDUTY_API_KEY:-}" ]; then
  echo "PagerDuty collector requires PAGERDUTY_API_KEY secret." >&2
  exit 0
fi

BASE_URL="${LUNAR_VAR_PAGERDUTY_BASE_URL:-https://api.pagerduty.com}"
BASE_URL="${BASE_URL%/}"
AUTH="Authorization: Token token=${LUNAR_SECRET_PAGERDUTY_API_KEY}"
ACCEPT="Accept: application/vnd.pagerduty+json;version=2"

pd_get() {
  local path="$1"
  set +e
  local response
  response="$(curl -fsS -H "$AUTH" -H "$ACCEPT" "${BASE_URL}${path}")"
  local status=$?
  set -e
  if [ $status -ne 0 ] || [ -z "$response" ]; then
    return 1
  fi
  echo "$response"
}

# Always write source metadata.
jq -n '{"tool": "pagerduty", "integration": "api"}' | lunar collect -j ".oncall.source" -

# Fetch service.
SERVICE_JSON="$(pd_get "/services/${SERVICE_ID}")" || {
  echo "Unable to fetch PagerDuty service ${SERVICE_ID}." >&2
  exit 0
}

SERVICE_NAME="$(echo "$SERVICE_JSON" | jq -r '.service.name // empty')"
SERVICE_STATUS="$(echo "$SERVICE_JSON" | jq -r '.service.status // empty')"
ESCALATION_POLICY_ID="$(echo "$SERVICE_JSON" | jq -r '.service.escalation_policy.id // empty')"

jq -n \
  --arg id "$SERVICE_ID" \
  --arg name "$SERVICE_NAME" \
  --arg status "$SERVICE_STATUS" \
  '{id: $id, name: $name, status: $status}' \
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
