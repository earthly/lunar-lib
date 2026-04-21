#!/bin/bash
set -e

FIND_CMD="${LUNAR_VAR_FIND_COMMAND:-find . -type f -name '*.json'}"

ENTRIES="$(
  eval "$FIND_CMD" 2>/dev/null | while IFS= read -r f; do
    [ -z "$f" ] && continue
    [ ! -f "$f" ] && continue
    if jq -e 'type == "object" and (.schemaVersion | type == "number") and (.panels | type == "array")' "$f" >/dev/null 2>&1; then
      rel="${f#./}"
      jq -c --arg path "$rel" '{path: $path, dashboard: .}' "$f"
    fi
  done | jq -s '.'
)"

COUNT="$(echo "$ENTRIES" | jq 'length')"
if [ "$COUNT" -gt 0 ]; then
  echo "$ENTRIES" | lunar collect -j ".observability.native.grafana.repo_dashboards" -
fi
