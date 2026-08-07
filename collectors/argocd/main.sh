#!/bin/bash
# Parses and validates ArgoCD custom resources (argoproj.io/*) into .cd.gitops
# on this component's own JSON.
set -e

# shellcheck source=collectors/argocd/parse.sh disable=SC1091
source "$(dirname "$0")/parse.sh"

RESULT=$(parse_argocd)

APP_COUNT=$(echo "$RESULT" | jq '.applications | length')
PROJ_COUNT=$(echo "$RESULT" | jq '.projects | length')

# Only collect when at least one argoproj resource was found (object presence
# is the signal — write nothing when ArgoCD isn't in use).
if [ "$APP_COUNT" -eq 0 ] && [ "$PROJ_COUNT" -eq 0 ]; then
    echo "No ArgoCD (argoproj.io) resources found, skipping." >&2
    exit 0
fi

echo "$RESULT" | lunar collect -j ".cd.gitops" -

# Source metadata.
TOOL_VERSION=$(kubeconform -v 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")
jq -n --arg v "$TOOL_VERSION" \
    '{tool: "argocd", integration: "code", validator: "kubeconform", validator_version: $v}' \
    | lunar collect -j ".cd.gitops.source" -
