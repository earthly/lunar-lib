#!/bin/bash
set -e

SERVICE_NAME=""
if [ -n "${LUNAR_COMPONENT_META:-}" ]; then
  SERVICE_NAME="$(echo "$LUNAR_COMPONENT_META" | jq -r '."datadog/service-name" // empty')"
fi
if [ -z "$SERVICE_NAME" ] && [ -n "${LUNAR_VAR_SERVICE_NAME:-}" ]; then
  SERVICE_NAME="$LUNAR_VAR_SERVICE_NAME"
fi

DASHBOARD_ID=""
if [ -n "${LUNAR_COMPONENT_META:-}" ]; then
  DASHBOARD_ID="$(echo "$LUNAR_COMPONENT_META" | jq -r '."datadog/dashboard-id" // empty')"
fi
if [ -z "$DASHBOARD_ID" ] && [ -n "${LUNAR_VAR_DASHBOARD_ID:-}" ]; then
  DASHBOARD_ID="$LUNAR_VAR_DASHBOARD_ID"
fi

if [ -z "$SERVICE_NAME" ] && [ -z "$DASHBOARD_ID" ]; then
  echo "No Datadog service tag or dashboard UUID found. Set 'datadog/service-name' or 'datadog/dashboard-id' meta, or the service_name/dashboard_id inputs." >&2
  exit 0
fi

if [ -z "${LUNAR_SECRET_DATADOG_API_KEY:-}" ] || [ -z "${LUNAR_SECRET_DATADOG_APP_KEY:-}" ]; then
  echo "Datadog collector requires DATADOG_API_KEY and DATADOG_APP_KEY secrets." >&2
  exit 0
fi

SITE="${LUNAR_VAR_DATADOG_SITE:-${DATADOG_SITE:-datadoghq.com}}"
API_BASE="https://api.${SITE}"
APP_BASE="https://app.${SITE}"

H_API="DD-API-KEY: ${LUNAR_SECRET_DATADOG_API_KEY}"
H_APP="DD-APPLICATION-KEY: ${LUNAR_SECRET_DATADOG_APP_KEY}"

jq -n '{"tool": "datadog", "integration": "api"}' | lunar collect -j ".observability.source" -

dd_get() {
  local path="$1"
  local response status
  set +e
  response="$(curl -fsS -H "$H_API" -H "$H_APP" "${API_BASE}${path}")"
  status=$?
  set -e
  if [ $status -ne 0 ]; then
    return 1
  fi
  echo "$response"
}

if [ -n "$SERVICE_NAME" ]; then
  jq -n --arg s "$SERVICE_NAME" '$s' | lunar collect -j ".observability.native.datadog.api.service_tag" -
fi

if [ -n "$DASHBOARD_ID" ]; then
  DASHBOARD_URL="${APP_BASE}/dashboard/${DASHBOARD_ID}"
  if DASHBOARD_JSON="$(dd_get "/api/v1/dashboard/${DASHBOARD_ID}")"; then
    jq -n \
      --arg id "$DASHBOARD_ID" \
      --arg url "$DASHBOARD_URL" \
      '{id: $id, exists: true, url: $url}' \
      | lunar collect -j ".observability.dashboard" -
    echo "$DASHBOARD_JSON" | lunar collect -j ".observability.native.datadog.api.dashboard" -
  else
    jq -n \
      --arg id "$DASHBOARD_ID" \
      '{id: $id, exists: false}' \
      | lunar collect -j ".observability.dashboard" -
  fi
fi

if [ -n "$SERVICE_NAME" ]; then
  MONITORS_JSON="[]"
  if RESP="$(dd_get "/api/v1/monitor?monitor_tags=service:${SERVICE_NAME}")"; then
    MONITORS_JSON="$RESP"
  fi
  ALERTS_COUNT="$(echo "$MONITORS_JSON" | jq 'length')"
  ALERTS_CONFIGURED=false
  if [ "$ALERTS_COUNT" -gt 0 ]; then
    ALERTS_CONFIGURED=true
  fi
  jq -n \
    --argjson configured "$ALERTS_CONFIGURED" \
    --argjson count "$ALERTS_COUNT" \
    '{configured: $configured, count: $count}' \
    | lunar collect -j ".observability.alerts" -
  echo "$MONITORS_JSON" | lunar collect -j ".observability.native.datadog.api.monitors" -

  SLOS_JSON="[]"
  if RESP="$(dd_get "/api/v1/slo?tags_query=service%3A${SERVICE_NAME}")"; then
    SLOS_JSON="$(echo "$RESP" | jq '.data // []')"
  fi
  SLO_COUNT="$(echo "$SLOS_JSON" | jq 'length')"
  SLO_DEFINED=false
  HAS_ERROR_BUDGET=false
  if [ "$SLO_COUNT" -gt 0 ]; then
    SLO_DEFINED=true
    BUDGET_HITS="$(echo "$SLOS_JSON" | jq '[.[] | (.thresholds // []) | .[] | select((.target // 100) < 100 or (.warning != null))] | length')"
    if [ "$BUDGET_HITS" -gt 0 ]; then
      HAS_ERROR_BUDGET=true
    fi
  fi
  jq -n \
    --argjson defined "$SLO_DEFINED" \
    --argjson count "$SLO_COUNT" \
    --argjson budget "$HAS_ERROR_BUDGET" \
    '{defined: $defined, count: $count, has_error_budget: $budget}' \
    | lunar collect -j ".observability.slo" -
  echo "$SLOS_JSON" | lunar collect -j ".observability.native.datadog.api.slos" -
fi
