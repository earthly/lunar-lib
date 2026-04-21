#!/bin/bash
set -e

DASHBOARD_UID=""
if [ -n "${LUNAR_COMPONENT_META:-}" ]; then
  DASHBOARD_UID="$(echo "$LUNAR_COMPONENT_META" | jq -r '."grafana/dashboard-uid" // empty')"
fi

if [ -z "$DASHBOARD_UID" ] && [ -n "${LUNAR_VAR_DASHBOARD_UID:-}" ]; then
  DASHBOARD_UID="$LUNAR_VAR_DASHBOARD_UID"
fi

if [ -z "$DASHBOARD_UID" ]; then
  echo "No Grafana dashboard UID found. Set 'grafana/dashboard-uid' meta or the dashboard_uid input." >&2
  exit 0
fi

if [ -z "${LUNAR_VAR_GRAFANA_BASE_URL:-}" ]; then
  echo "Grafana collector requires grafana_base_url input." >&2
  exit 0
fi

if [ -z "${LUNAR_SECRET_GRAFANA_API_KEY:-}" ]; then
  echo "Grafana collector requires GRAFANA_API_KEY secret." >&2
  exit 0
fi

BASE_URL="${LUNAR_VAR_GRAFANA_BASE_URL%/}"
AUTH="Authorization: Bearer ${LUNAR_SECRET_GRAFANA_API_KEY}"

jq -n '{"tool": "grafana", "integration": "api"}' | lunar collect -j ".observability.source" -

grafana_get() {
  local path="$1"
  local response status
  set +e
  response="$(curl -fsS -H "$AUTH" "${BASE_URL}${path}")"
  status=$?
  set -e
  if [ $status -ne 0 ]; then
    return 1
  fi
  echo "$response"
}

DASHBOARD_JSON=""
DASHBOARD_EXISTS=false
DASHBOARD_URL=""
FOLDER_UID=""

if DASHBOARD_JSON="$(grafana_get "/api/dashboards/uid/${DASHBOARD_UID}")"; then
  DASHBOARD_EXISTS=true
  DASHBOARD_PATH="$(echo "$DASHBOARD_JSON" | jq -r '.meta.url // empty')"
  if [ -n "$DASHBOARD_PATH" ]; then
    DASHBOARD_URL="${BASE_URL}${DASHBOARD_PATH}"
  fi
  FOLDER_UID="$(echo "$DASHBOARD_JSON" | jq -r '.meta.folderUid // empty')"
fi

if [ "$DASHBOARD_EXISTS" = "true" ]; then
  jq -n \
    --arg id "$DASHBOARD_UID" \
    --arg url "$DASHBOARD_URL" \
    '{id: $id, exists: true, url: $url}' \
    | lunar collect -j ".observability.dashboard" -
  echo "$DASHBOARD_JSON" | lunar collect -j ".observability.native.grafana.api.dashboard" -
else
  jq -n \
    --arg id "$DASHBOARD_UID" \
    '{id: $id, exists: false}' \
    | lunar collect -j ".observability.dashboard" -
fi

ALERTS_COUNT=0
ALERTS_CONFIGURED=false
ALERT_RULES_JSON=""

if [ "$DASHBOARD_EXISTS" = "true" ] && [ -n "$FOLDER_UID" ]; then
  if ALERT_RULES_RAW="$(grafana_get "/api/v1/provisioning/alert-rules")"; then
    ALERT_RULES_JSON="$(echo "$ALERT_RULES_RAW" | jq --arg fuid "$FOLDER_UID" '[.[] | select(.folderUID == $fuid)]')"
    ALERTS_COUNT="$(echo "$ALERT_RULES_JSON" | jq 'length')"
    if [ "$ALERTS_COUNT" -gt 0 ]; then
      ALERTS_CONFIGURED=true
    fi
  fi
fi

jq -n \
  --argjson configured "$ALERTS_CONFIGURED" \
  --argjson count "$ALERTS_COUNT" \
  '{configured: $configured, count: $count}' \
  | lunar collect -j ".observability.alerts" -

if [ -n "$ALERT_RULES_JSON" ]; then
  echo "$ALERT_RULES_JSON" | lunar collect -j ".observability.native.grafana.api.alert_rules" -
fi
