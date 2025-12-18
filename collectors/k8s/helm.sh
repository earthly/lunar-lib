#!/bin/bash

# Function to detect if content is a Helm template.
# Helm templates can look a lot like native Kubernetes yaml,
# but we can detect them by looking for specific Helm template directives or values file patterns.
is_helm_template() {
  local content="$1"
  
  # Check for Helm template syntax (Go templates)
  if echo "$content" | grep -qE '{{[[:space:]]*-?[[:space:]]*\.(Values?|Release|Chart)\.[^}]*}}|{{[[:space:]]*-?[[:space:]]*include[^}]*}}|{{[[:space:]]*-[[:space:]]*if[^}]*}}' 2>/dev/null; then
    return 0
  fi

  # Check for Helm values file patterns
  if echo "$content" | grep -qE '^[[:space:]]*# --.*$|^[[:space:]]*nameOverride[[:space:]]*:|^[[:space:]]*fullnameOverride[[:space:]]*:|^[[:space:]]*global[[:space:]]*:' 2>/dev/null; then
    return 0
  fi

  return 1
}
