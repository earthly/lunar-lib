#!/bin/bash

set -e

# Find all Dockerfiles and process them into JSON ASTs
find . -name 'Dockerfile' -o -name '*.Dockerfile' | while read -r file; do
  json=$(dockerfile-json "$file")
  echo "{\"path\":\"${file#./}\", \"json\": $json}"
done > dockerfile_objects.json
# Combine the JSON objects into an array
jq -s '.' dockerfile_objects.json > delta1.json
# Submit component JSON delta.
cat delta1.json | lunar collect -j ".dockerfile.asts" -

#
# Use the ASTs to extract additional information.

# Extract referenced base images.
jq '[.[] | {path: .path, images: [((.json.Stages // [])[] | (.From.Image // empty))]}]' delta1.json > delta2.json

# Submit component JSON delta.
cat delta2.json | lunar collect -j ".dockerfile.images_summary" -

# Extract labels by stage.
jq '[.[] | {path: .path, stages: [((.json.Stages // []) | to_entries[] | {stage_index: .key, base_name: .value.BaseName, labels: ((.value.Commands // []) | map(select(.Name == "LABEL") | (.Labels // [])) | flatten | map({(.Key): .Value}) | add // {})})]}]' delta1.json > delta3.json
# Submit component JSON delta.
cat delta3.json | lunar collect -j ".dockerfile.labels_summary" -
