#!/bin/bash
set -e

# CI collector - runs native on CI runner, avoid jq and heavy dependencies

# Convert LUNAR_CI_COMMAND from JSON array to string if needed
CMD_RAW="$LUNAR_CI_COMMAND"
if [[ "$CMD_RAW" == "["* ]]; then
    CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
    CMD_STR="$CMD_RAW"
fi

# Use the exact traced binary for version extraction
PHP_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-php}"

# Collect PHP version from the traced binary
version=$("$PHP_BIN" -v 2>/dev/null | head -1 | awk '{print $2}' || echo "")

if [[ -n "$version" ]]; then
  # Escape backslashes first, then quotes, for valid JSON
  CMD_ESCAPED=$(echo "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

  # Write cicd command entry (no jq required)
  # Multiple php/composer commands in same CI run will each append to the cmds array
  echo "{\"cmds\":[{\"cmd\":\"$CMD_ESCAPED\",\"version\":\"$version\"}],\"source\":{\"tool\":\"php\",\"integration\":\"ci\"}}" | \
    lunar collect -j ".lang.php.cicd" -
fi
