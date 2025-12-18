#!/bin/bash

set -e

# Function to process a single Helm chart directory
process_chart() {
  local chart_dir="$1"

  # Validate the Helm chart using helm lint
  set +e
  validation_output="$(helm lint "$chart_dir" 2>&1)"
  status=$?
  set -e

  if [ $status -eq 0 ]; then
    valid=true
    validation_error=null
  else
    valid=false
    validation_error="$validation_output"
  fi

  # Build JSON object for this result
  obj="$(
    jq -n \
      --arg chart_location "$chart_dir" \
      --argjson valid "$valid" \
      --arg validation_error "$validation_error" \
      '{
        chart_location: $chart_location,
        valid: $valid,
      } + (if $validation_error == "null" then {} else {validation_error: $validation_error} end)'
  )"

  # Output the JSON object
  echo "$obj"
}

# Export function for parallel processing
export -f process_chart

# Find all unique directories containing Chart.yaml or Chart.yml
# Process them in parallel, which can improve performance on large repositories.
find . -name "Chart.yaml" -o -name "Chart.yml" | \
  xargs -I {} dirname {} | \
  sort -u | \
  parallel -j 4 process_chart | \
  jq -s '{charts: .}' | \
  lunar collect -j ".helm" -
