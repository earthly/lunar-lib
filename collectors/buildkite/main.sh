#!/bin/bash

set -e

process_pipeline() {
  local pipeline_dir="$1"
  local pipeline_file

  if [ -f "$pipeline_dir/pipeline.yml" ]; then
    pipeline_file="$pipeline_dir/pipeline.yml"
  elif [ -f "$pipeline_dir/pipeline.yaml" ]; then
    pipeline_file="$pipeline_dir/pipeline.yaml"
  fi

  # Parse the pipeline YAML file to JSON
  pipeline_yaml="$(yq eval -o=json '.' "$pipeline_file" 2>/dev/null | jq -cs .)"

  # Build JSON object for this result
  obj="$(
    jq -n \
      --arg pipeline_location "$pipeline_file" \
      --argjson pipeline_yaml "$pipeline_yaml" \
      '{
        pipeline_location: $pipeline_location,
        pipeline: $pipeline_yaml
      }'
  )"

  # Output the JSON object
  echo "$obj"
}

export -f process_pipeline

find . -name "pipeline.yml" -o -name "pipeline.yaml" | \
  xargs -I {} dirname {} | \
  sort -u | \
  parallel -j 4 process_pipeline | \
  jq -s '{pipelines: .}' | \
  lunar collect -j ".buildkite" -