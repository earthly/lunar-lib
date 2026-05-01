#!/bin/bash
set -e

IFS=',' read -ra CANDIDATES <<< "$LUNAR_VAR_GITMODULES_PATHS"

CONFIG_FILE=""
for candidate in "${CANDIDATES[@]}"; do
  if [ -f "./$candidate" ]; then
    CONFIG_FILE="./$candidate"
    break
  fi
done

if [ -z "$CONFIG_FILE" ]; then
  exit 0
fi

PATH_NORMALIZED="${CONFIG_FILE#./}"

# git config --file ... --list dumps the .gitmodules INI in
# `submodule.<name>.<key>=<value>` form, which is far easier to parse than
# the raw INI.
if ! LISTING=$(git config --file "$CONFIG_FILE" --list 2>/dev/null); then
  jq -n --arg path "$PATH_NORMALIZED" \
    '{valid: false, path: $path}' \
    | lunar collect -j ".git.submodules" -
  exit 0
fi

MODULES_JSON=$(awk -F= '
  {
    key = $1
    sub(/^[[:space:]]+/, "", key)
    sub(/[[:space:]]+$/, "", key)
    value = $0
    sub(/^[^=]*=/, "", value)
    if (key !~ /^submodule\./) next
    sub(/^submodule\./, "", key)
    nameEnd = index(key, ".")
    if (nameEnd == 0) next
    name = substr(key, 1, nameEnd - 1)
    field = substr(key, nameEnd + 1)
    gsub(/"/, "\\\"", name)
    gsub(/"/, "\\\"", value)
    printf "{\"name\":\"%s\",\"field\":\"%s\",\"value\":\"%s\"}\n", name, field, value
  }
' <<< "$LISTING" | jq -s '
  group_by(.name) | map({
    name: .[0].name,
    path: ([.[] | select(.field == "path") | .value][0] // null),
    url:  ([.[] | select(.field == "url")  | .value][0] // null),
    branch: ([.[] | select(.field == "branch") | .value][0] // null)
  })
' 2>/dev/null || echo "[]")

if [ -z "$MODULES_JSON" ] || [ "$MODULES_JSON" = "null" ]; then
  MODULES_JSON="[]"
fi

jq -n \
  --arg path "$PATH_NORMALIZED" \
  --argjson modules "$MODULES_JSON" \
  '{
    valid: true,
    path: $path,
    modules: $modules
  }' | lunar collect -j ".git.submodules" -
