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

# `kubectl version --client` output varies by version:
#   kubectl 1.28+: "Client Version: v1.32.0"
#   kubectl ≤ 1.27: "Client Version: version.Info{Major:"1", Minor:"27", GitVersion:"v1.27.3", ...}"
# Match the v-prefixed semver anywhere on the "Client Version" line, preserving vendor
# build metadata (e.g. "1.28.2-eks-4ea7009", "1.28.4-gke.10083003") via [^ ,"}]*.
VERSION=$("$KUBECTL_BIN" version --client 2>/dev/null \
  | awk '/Client Version/ {if (match($0, /v[0-9]+\.[0-9]+\.[0-9]+[^ ,"}]*/)) {v = substr($0, RSTART, RLENGTH); sub(/^v/, "", v); print v; exit}}' \
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
