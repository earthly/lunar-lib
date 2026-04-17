#!/bin/bash
set -e

IFS=',' read -ra CANDIDATES <<< "$LUNAR_VAR_PATHS"

CONFIG_FILE=""
for candidate in "${CANDIDATES[@]}"; do
  if [ -f "./$candidate" ]; then
    CONFIG_FILE="./$candidate"
    break
  fi
done

if [ -z "$CONFIG_FILE" ]; then
  lunar collect -j ".dep_automation.dependabot.exists" false
  exit 0
fi

PATH_NORMALIZED="${CONFIG_FILE#./}"

# Parse YAML → JSON
if ! CONFIG_JSON=$(yq -o json "$CONFIG_FILE" 2>/dev/null) || [ -z "$CONFIG_JSON" ] || [ "$CONFIG_JSON" = "null" ]; then
  jq -n --arg path "$PATH_NORMALIZED" \
    '{exists: true, valid: false, path: $path, updates: [], ecosystems: [], update_count: 0}' \
    | lunar collect -j ".dep_automation.dependabot" -
  exit 0
fi

VERSION=$(echo "$CONFIG_JSON" | jq -r '.version // empty')

UPDATES=$(echo "$CONFIG_JSON" | jq -c '
  (.updates // []) | map({
    package_ecosystem: ."package-ecosystem",
    directory: (.directory // "/"),
    schedule: (.schedule.interval // null),
    open_pull_requests_limit: ."open-pull-requests-limit"
  } | with_entries(select(.value != null)))
')

ECOSYSTEMS=$(echo "$CONFIG_JSON" | jq -c '
  [(.updates // [])[] | ."package-ecosystem" | select(. != null and . != "")] | unique
')

UPDATE_COUNT=$(echo "$UPDATES" | jq 'length')

# Build output — include version only if present, as an integer if numeric
if [ -n "$VERSION" ]; then
  RESULT=$(jq -n \
    --arg path "$PATH_NORMALIZED" \
    --arg version "$VERSION" \
    --argjson updates "$UPDATES" \
    --argjson ecosystems "$ECOSYSTEMS" \
    --argjson update_count "$UPDATE_COUNT" \
    '{
      exists: true,
      valid: true,
      path: $path,
      version: ($version | tonumber? // $version),
      updates: $updates,
      ecosystems: $ecosystems,
      update_count: $update_count
    }')
else
  RESULT=$(jq -n \
    --arg path "$PATH_NORMALIZED" \
    --argjson updates "$UPDATES" \
    --argjson ecosystems "$ECOSYSTEMS" \
    --argjson update_count "$UPDATE_COUNT" \
    '{
      exists: true,
      valid: true,
      path: $path,
      updates: $updates,
      ecosystems: $ecosystems,
      update_count: $update_count
    }')
fi

echo "$RESULT" | lunar collect -j ".dep_automation.dependabot" -
