#!/bin/bash
set -e

# Record helm commands in CI with the helm version that ran them.
# Native-bash: no jq dependency (CI collectors run on the user's runner).

# Parse LUNAR_CI_COMMAND JSON array into a command string (pure bash)
CMD_STR=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')

# Escape for safe JSON embedding (backslashes then double quotes)
json_cmd=$(echo "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

# Get Helm version using the exact traced binary
HELM_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-helm}"
version=$("$HELM_BIN" version --template='{{.Version}}' 2>/dev/null | sed 's/^v//' || true)

lunar collect -j ".k8s.helm.cicd.cmds" \
    "[{\"cmd\": \"$json_cmd\", \"version\": \"$version\"}]"
lunar collect -j ".k8s.helm.cicd.source" \
    '{"tool": "helm", "integration": "ci"}'
