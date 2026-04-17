#!/bin/bash
set -e

SCRIPT_DIR="$(dirname "$0")"

IFS=',' read -ra CANDIDATES <<< "$LUNAR_VAR_PATHS"

CONFIG_FILE=""
CONFIG_JSON=""
for candidate in "${CANDIDATES[@]}"; do
  [ -f "./$candidate" ] || continue

  # parse_renovate.py:
  #   exit 0 → parsed JSON on stdout
  #   exit 2 → package.json without "renovate" key (keep searching)
  #   exit 1 → file exists but failed to parse (stop; mark valid:false)
  if parsed=$(python3 "$SCRIPT_DIR/parse_renovate.py" "./$candidate" 2>/dev/null); then
    CONFIG_FILE="./$candidate"
    CONFIG_JSON="$parsed"
    break
  else
    rc=$?
    if [ "$rc" = "2" ]; then
      continue
    fi
    # Parse failure — record it at this path
    CONFIG_FILE="./$candidate"
    CONFIG_JSON=""
    break
  fi
done

if [ -z "$CONFIG_FILE" ]; then
  lunar collect -j ".dep_automation.renovate.exists" false
  exit 0
fi

PATH_NORMALIZED="${CONFIG_FILE#./}"

if [ -z "$CONFIG_JSON" ]; then
  jq -n --arg path "$PATH_NORMALIZED" \
    '{exists: true, valid: false, path: $path, extends: [], all_managers_enabled: false, enabled_managers: []}' \
    | lunar collect -j ".dep_automation.renovate" -
  exit 0
fi

# Normalized summary for policies
EXTENDS=$(echo "$CONFIG_JSON" | jq -c '
  (.extends // []) | if type == "string" then [.] else . end
')

if echo "$CONFIG_JSON" | jq -e 'has("enabledManagers")' >/dev/null 2>&1; then
  ENABLED_MANAGERS=$(echo "$CONFIG_JSON" | jq -c '.enabledManagers // []')
  ALL_MANAGERS_ENABLED="false"
else
  ENABLED_MANAGERS="[]"
  ALL_MANAGERS_ENABLED="true"
fi

jq -n \
  --arg path "$PATH_NORMALIZED" \
  --argjson extends "$EXTENDS" \
  --argjson all_managers_enabled "$ALL_MANAGERS_ENABLED" \
  --argjson enabled_managers "$ENABLED_MANAGERS" \
  '{
    exists: true,
    valid: true,
    path: $path,
    extends: $extends,
    all_managers_enabled: $all_managers_enabled,
    enabled_managers: $enabled_managers
  }' | lunar collect -j ".dep_automation.renovate" -

# Full raw config verbatim
echo "$CONFIG_JSON" | lunar collect -j ".dep_automation.native.renovate" -
