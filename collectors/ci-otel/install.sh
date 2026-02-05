#!/bin/bash
set -e

# Verify required dependencies (must be pre-installed in CI environment)
for dep in curl jq; do
  if ! command -v "$dep" >/dev/null 2>&1; then
    echo "ERROR: Missing required dependency '$dep'. Please install it in your CI runner." >&2
    exit 1
  fi
done

# xxd is optional (only used as fallback for span ID generation in debug scenarios)
# Try to install it if not available, but don't fail if we can't
if ! command -v xxd >/dev/null 2>&1; then
  echo "Installing xxd (optional, for span ID generation fallback)..."
  if command -v apk >/dev/null 2>&1; then
    apk add --no-cache xxd 2>/dev/null || true
  elif command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq && apt-get install -y -qq xxd 2>/dev/null || apt-get install -y -qq vim-common 2>/dev/null || true
  elif command -v yum >/dev/null 2>&1; then
    yum install -y vim-common 2>/dev/null || true
  fi
fi

echo "ci-otel collector dependencies verified"

