#!/bin/bash
set -e

# Write source metadata - presence signals codecov ran
lunar collect ".testing.coverage.source.tool" "codecov"
lunar collect ".testing.coverage.source.integration" "ci"

# Try to get codecov version
if command -v codecov &>/dev/null; then
  VERSION=$(codecov --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' || echo "")
  if [ -n "$VERSION" ]; then
    lunar collect ".testing.coverage.source.version" "$VERSION"
  fi
fi
