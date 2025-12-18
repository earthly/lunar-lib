#!/bin/bash
set -e

process_file() {
  local f="$1"

  # Parse all YAML docs in the file
  set +e
  all_docs=$(yq eval -o=json '.' "$f" 2>/dev/null | jq -cs '.')
  set -e

  # Filter to only Backstage catalog docs
  set +e
  catalog_json=$(echo "$all_docs" | jq -c '[.[] | select(.apiVersion == "backstage.io/v1alpha1")]')
  set -e

  # If no Backstage docs found, skip this file
  if [ -z "$catalog_json" ] || [ "$catalog_json" = "[]" ] || [ "$catalog_json" = "null" ]; then
    return
  fi

  # Validate using backstage validator
  set +e
  validation_msg=$(validate-entity "$f" 2>&1 1>/dev/null)
  validation_exit=$?
  set -e
  
  if [ $validation_exit -ne 0 ]; then
    valid=false
    validation_error="$validation_msg"
    catalog_as_string="$(cat "$f" 2>/dev/null)"
  else
    valid=true
    validation_error=null
    catalog_as_string=""
  fi

  obj=$(jq -n \
    --arg catalog_location "$f" \
    --argjson catalog "$catalog_json" \
    --argjson valid "$valid" \
    --arg validation_error "$validation_error" \
    --arg catalog_as_string "$catalog_as_string" \
    '{
      catalog_location: $catalog_location,
      catalog: $catalog,
      valid: $valid
    }
    + (if $validation_error == "null" then {} else {validation_error: $validation_error} end)
    + (if ($catalog_as_string | length) > 0 then {catalog_as_string: $catalog_as_string} else {} end)')

  echo "$obj"
}

export -f process_file

git ls-files '*.yaml' '*.yml' | \
  parallel -j 24 process_file | \
  jq -s '{catalogs: .}' | \
  lunar collect -j ".backstage" -
