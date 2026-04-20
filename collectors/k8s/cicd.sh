#!/bin/bash
set -e

# CI collector - runs native on CI runner, avoid jq and heavy dependencies.
# Records every kubectl command with the kubectl client version.

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
KUBECTL_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-kubectl}"

# `kubectl version --client` prints e.g. "Client Version: v1.29.2"
# Fall back to older output formats ("Client Version: version.Info{...GitVersion:\"v1.29.2\"...}")
VERSION=$("$KUBECTL_BIN" version --client 2>/dev/null \
  | awk '/Client Version/ {for (i=1; i<=NF; i++) if ($i ~ /^v?[0-9]+\.[0-9]+\.[0-9]+/) {gsub(/[",}]/, "", $i); sub(/^v/, "", $i); print $i; exit}}' \
  || echo "")
VERSION_ESCAPED=$(echo "$VERSION" | sed 's/\\/\\\\/g; s/"/\\"/g')

# Always collect the command; version may be empty
if [[ -n "$VERSION_ESCAPED" ]]; then
  echo "{\"cmds\":[{\"cmd\":\"$CMD_ESCAPED\",\"version\":\"$VERSION_ESCAPED\"}],\"source\":{\"tool\":\"kubectl\",\"integration\":\"ci\"}}" | \
    lunar collect -j ".k8s.cicd" -
else
  echo "{\"cmds\":[{\"cmd\":\"$CMD_ESCAPED\"}],\"source\":{\"tool\":\"kubectl\",\"integration\":\"ci\"}}" | \
    lunar collect -j ".k8s.cicd" -
fi
