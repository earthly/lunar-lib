#!/bin/bash
set -e

# Install xxd if not available
if ! command -v xxd >/dev/null 2>&1; then
  echo "Installing xxd..."
  if command -v apk >/dev/null 2>&1; then
    apk add --no-cache xxd
  elif command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq && apt-get install -y -qq xxd || apt-get install -y -qq vim-common
  elif command -v yum >/dev/null 2>&1; then
    yum install -y vim-common
  else
    echo "Warning: No supported package manager found (apk/apt-get/yum). xxd may not be available." >&2
  fi
fi

echo "ci-otel collector dependencies verified"

