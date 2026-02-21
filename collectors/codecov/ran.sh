#!/bin/bash
set -e

# Write source metadata - presence signals codecov ran
lunar collect ".testing.coverage.source.tool" "codecov"
lunar collect ".testing.coverage.source.integration" "ci"

# Get codecov version using the exact traced binary
CODECOV_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-codecov}"
VERSION=$("$CODECOV_BIN" --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' || echo "")
if [ -n "$VERSION" ]; then
  lunar collect ".testing.coverage.source.version" "$VERSION"
fi
