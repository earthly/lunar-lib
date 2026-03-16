#!/bin/bash
set -e

# CI collector - runs native on CI runner, avoid jq and heavy dependencies
# Tracks Composer commands in CI with Composer version

# Convert LUNAR_CI_COMMAND from JSON array to string if needed
CMD_RAW="$LUNAR_CI_COMMAND"
if [[ "$CMD_RAW" == "["* ]]; then
    CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
    CMD_STR="$CMD_RAW"
fi

# Use the exact traced binary for version extraction
COMPOSER_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-composer}"

# Collect Composer CI/CD command information
version=$("$COMPOSER_BIN" --version 2>/dev/null | sed -n 's/.*Composer version \([0-9][0-9.]*\).*/\1/p' || echo "")

if [[ -n "$version" ]]; then
  # Escape backslashes first, then quotes, for valid JSON
  CMD_ESCAPED=$(echo "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

  # Write cicd command entry (no jq required)
  echo "{\"cmds\":[{\"cmd\":\"$CMD_ESCAPED\",\"version\":\"$version\"}],\"source\":{\"tool\":\"composer\",\"integration\":\"ci\"}}" | \
    lunar collect -j ".lang.php.composer.cicd" -
fi
