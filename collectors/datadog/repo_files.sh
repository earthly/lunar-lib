#!/bin/bash
set -e

FIND_CMD="${LUNAR_VAR_FIND_COMMAND:-find . -type f -name '*.json'}"

FILES="$(eval "$FIND_CMD" 2>/dev/null)"

DASHBOARD_ENTRIES="$(
  echo "$FILES" | while IFS= read -r f; do
    [ -z "$f" ] && continue
    [ ! -f "$f" ] && continue
    if jq -e 'type == "object" and (.widgets | type == "array") and (.layout_type | type == "string")' "$f" >/dev/null 2>&1; then
      rel="${f#./}"
      jq -c --arg path "$rel" '{path: $path, dashboard: .}' "$f"
    fi
  done | jq -s '.'
)"

MONITOR_ENTRIES="$(
  echo "$FILES" | while IFS= read -r f; do
    [ -z "$f" ] && continue
    [ ! -f "$f" ] && continue
    if jq -e 'type == "object" and (.type | type == "string") and (.query | type == "string") and (.name | type == "string")' "$f" >/dev/null 2>&1; then
      rel="${f#./}"
      jq -c --arg path "$rel" '{path: $path, monitor: .}' "$f"
    fi
  done | jq -s '.'
)"

DASHBOARD_COUNT="$(echo "$DASHBOARD_ENTRIES" | jq 'length')"
if [ "$DASHBOARD_COUNT" -gt 0 ]; then
  echo "$DASHBOARD_ENTRIES" | lunar collect -j ".observability.native.datadog.repo_dashboards" -
fi

MONITOR_COUNT="$(echo "$MONITOR_ENTRIES" | jq 'length')"
if [ "$MONITOR_COUNT" -gt 0 ]; then
  echo "$MONITOR_ENTRIES" | lunar collect -j ".observability.native.datadog.repo_monitors" -
fi
