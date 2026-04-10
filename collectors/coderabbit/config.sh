#!/bin/bash
set -e

# Detect CodeRabbit configuration files (.coderabbit.yaml or .coderabbit.yml).

CONFIG_FILE=""
if [ -f ".coderabbit.yaml" ]; then
  CONFIG_FILE=".coderabbit.yaml"
elif [ -f ".coderabbit.yml" ]; then
  CONFIG_FILE=".coderabbit.yml"
fi

if [ -z "$CONFIG_FILE" ]; then
  jq -n '{
    config_exists: false
  }' | lunar collect -j ".ai.native.coderabbit" -
  exit 0
fi

jq -n \
  --arg config_file "$CONFIG_FILE" \
  --argjson config_exists true \
  '{
    config_file: $config_file,
    config_exists: $config_exists
  }' | lunar collect -j ".ai.native.coderabbit" -
