#!/bin/bash

set -e

# Source helper function for helm
source "$LUNAR_PLUGIN_ROOT/helm.sh"

# Directories to ignore
IGNORE_DIRS=(
  ".github"
  ".git"
  "node_modules"
  "vendor"
  "templates"
  "charts"
  "helm"
  "openapi"
)

# File names to ignore
IGNORE_FILES=(
  "catalog-info.yaml"
  "catalog-info.yml"
  "Chart.yaml"
  "Chart.yml"
)

# Function to process a single file
process_file() {
  local f="$1"

  # Read file content once for all checks
  content="$(cat "$f")"

  # Skip files that don't look like K8s manifests: require top-level .apiVersion and .kind
  set +e
  yq -e '.apiVersion and .kind' "$f" >/dev/null 2>&1
  has_top_keys=$?
  set -e
  if [ $has_top_keys -ne 0 ]; then
    return 0
  fi

  # Skip Helm templates, which look like K8s manifests 
  # but cannot be validated the same way.
  if is_helm_template "$content"; then
    return 0
  fi

  # Validate the k8s manifest using kubeconform
  set +e
  validation_output="$(kubeconform -strict -ignore-missing-schemas "$f" 2>&1)"
  status=$?
  set -e

  if [ $status -eq 0 ]; then
    valid=true
    validation_error=null
  else
    valid=false
    validation_error="$validation_output"
  fi

  # Convert YAML manifest to JSON (yq will fail gracefully if YAML is invalid)
  contents="$(echo "$content" | yq -o=json '.' 2>/dev/null || echo '{}')"

  # Build JSON object for this file using temp file approach
  temp_contents=$(mktemp)
  echo "$contents" >"$temp_contents"
  obj="$(
    jq -n \
      --arg k8s_file_location "$f" \
      --argjson valid "$valid" \
      --slurpfile contents "$temp_contents" \
      --arg validation_error "$validation_error" \
      '{
        k8s_file_location: $k8s_file_location,
        valid: $valid,
        contents: $contents[0]
      } + (if $validation_error == "null" then {} else {validation_error: $validation_error} end)'
  )"

  # Output the JSON object (will be collected by parallel)
  echo "$obj"
}

# Export function and variables for parallel processing
export -f process_file
export -f is_helm_template

# Process files in parallel using GNU parallel to improve performance in large repos.
# Filter out ignored files before passing them in for processing.
git ls-files '*.yaml' '*.yml' | \
  grep -vE "(^|/)($(IFS='|'; echo "${IGNORE_DIRS[*]}"))(/|$)" | \
  grep -vE "($(IFS='|'; echo "${IGNORE_FILES[*]}"))$" | \
  parallel -j 4 process_file | jq -s '{descriptors: .}' | lunar collect -j ".k8s" -
