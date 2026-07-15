#!/bin/bash
set -e

# CI collector - runs native on CI runner, avoid jq and heavy dependencies.
# Records every istioctl command with the istioctl client version.

# Convert LUNAR_CI_COMMAND from JSON array to string if needed
CMD_RAW="$LUNAR_CI_COMMAND"
if [[ "$CMD_RAW" == "["* ]]; then
    CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
    CMD_STR="$CMD_RAW"
fi

# Escape command for safe JSON embedding (backslashes then double quotes)
CMD_ESCAPED=$(echo "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

# Use the exact traced binary for version extraction
ISTIOCTL_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-istioctl}"

# `istioctl version --remote=false` prints the client version. Output varies:
#   "1.22.0"                        (newer, --short-like default)
#   "client version: 1.22.0"        (older)
# Match the first semver anywhere in the output. --remote=false avoids a cluster call.
VERSION=$("$ISTIOCTL_BIN" version --remote=false 2>/dev/null \
  | grep -oE '[0-9]+\.[0-9]+\.[0-9]+[^ ,"}]*' | head -1 \
  || echo "")
VERSION_ESCAPED=$(echo "$VERSION" | sed 's/\\/\\\\/g; s/"/\\"/g')

# Always collect the command; version may be empty
if [[ -n "$VERSION_ESCAPED" ]]; then
  echo "{\"cmds\":[{\"cmd\":\"$CMD_ESCAPED\",\"version\":\"$VERSION_ESCAPED\"}],\"source\":{\"tool\":\"istioctl\",\"integration\":\"ci\"}}" | \
    lunar collect -j ".mesh.cicd" -
else
  echo "{\"cmds\":[{\"cmd\":\"$CMD_ESCAPED\"}],\"source\":{\"tool\":\"istioctl\",\"integration\":\"ci\"}}" | \
    lunar collect -j ".mesh.cicd" -
fi
