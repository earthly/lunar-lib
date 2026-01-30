#!/bin/bash
set -e

# Install xxd if not available (part of vim-common or xxd package)
if ! command -v xxd >/dev/null 2>&1; then
  echo "Installing xxd..."
  apt-get update -qq && apt-get install -y -qq xxd || apt-get install -y -qq vim-common
fi

echo "ci-otel collector dependencies verified"

