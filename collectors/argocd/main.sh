#!/bin/bash
set -e

process_file() {
  local f="$1"

  # Parse all YAML docs in the file
  set +e
  all_docs=$(yq eval -o=json '.' "$f" 2>/dev/null | jq -cs '.')
  set -e

  # Filter to only ArgoCD docs
  set +e
  argocd_json=$(echo "$all_docs" | jq -c '[.[] | select(.apiVersion == "argoproj.io/v1alpha1")]')
  set -e

  # If no ArgoCD docs found, skip this file
  if [ -z "$argocd_json" ] || [ "$argocd_json" = "[]" ] || [ "$argocd_json" = "null" ]; then
    return
  fi

  # Build JSON object for this result
  obj="$(
    jq -n \
      --argjson argocd_json "$argocd_json" \
      '{
        application: $argocd_json
      }'
  )"

  # Output the JSON object
  echo "$obj"
}

export -f process_file

git ls-files '*.yaml' '*.yml' | \
  parallel -j 4 process_file | \
  jq -s '{applications: .}' | \
  lunar collect -j ".argocd" -