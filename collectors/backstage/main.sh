#!/bin/bash

set -e

SCRIPT_DIR="$(dirname "$0")"

IFS=',' read -ra CANDIDATES <<< "$LUNAR_VAR_PATHS"

CATALOG_FILE=""
for candidate in "${CANDIDATES[@]}"; do
  if [ -f "./$candidate" ]; then
    CATALOG_FILE="./$candidate"
    break
  fi
done

if [ -z "$CATALOG_FILE" ]; then
  # No catalog-info.yaml found — write nothing. Absence of `.catalog.native.backstage`
  # IS the signal. Policies use Check.exists(".catalog.native.backstage") to detect.
  exit 0
fi

PATH_NORMALIZED="${CATALOG_FILE#./}"

YQ_ERR=$(mktemp)
trap 'rm -f "$YQ_ERR"' EXIT

if PARSED_JSON=$(yq -o=json '.' "$CATALOG_FILE" 2>"$YQ_ERR"); then
  RESULT=$(echo "$PARSED_JSON" | python3 "$SCRIPT_DIR/lint_backstage.py" --path "$PATH_NORMALIZED")
else
  ERR_MSG=$(tr '\n' ' ' < "$YQ_ERR" | sed 's/[[:space:]]*$//' | head -c 500)
  [ -z "$ERR_MSG" ] && ERR_MSG="YAML parse error"
  RESULT=$(jq -n \
    --arg path "$PATH_NORMALIZED" \
    --arg msg "$ERR_MSG" \
    '{
      valid: false,
      errors: [{line: 0, message: $msg, severity: "error"}],
      path: $path
    }')
fi

echo "$RESULT" | lunar collect -j ".catalog.native.backstage" -
