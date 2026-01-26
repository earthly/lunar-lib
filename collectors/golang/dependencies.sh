#!/bin/bash
set -e

# Collect Go module dependencies into .lang.go.dependencies
# Note: License information should be collected via SBOM tools (Syft, Trivy, etc.)

# Check if this is actually a Go project by looking for go.mod
if [[ ! -f "go.mod" ]]; then
    echo "No go.mod found, exiting"
    exit 0
fi

# Process modules and build JSON
direct_deps=()
transitive_deps=()

while IFS= read -r mod_json; do
  if [[ -z "$mod_json" ]]; then
    continue
  fi
  
  path=$(echo "$mod_json" | jq -r '.Path // ""')
  version=$(echo "$mod_json" | jq -r '.Version // ""')
  indirect=$(echo "$mod_json" | jq -r '.Indirect // false')
  main=$(echo "$mod_json" | jq -r '.Main // false')
  replace=$(echo "$mod_json" | jq -r '.Replace // null')
  
  # Skip main module
  if [[ "$main" == "true" ]]; then
    continue
  fi
  
  # Build dependency object
  dep_obj=$(jq -n \
    --arg path "$path" \
    --arg version "$version" \
    --argjson indirect "$indirect" \
    --argjson replace "$replace" \
    '{
      path: $path,
      version: $version,
      indirect: $indirect,
      replace: (if $replace then {path: $replace.Path, version: ($replace.Version // "")} else null end)
    }')
  
  if [[ "$indirect" == "true" ]]; then
    transitive_deps+=("$dep_obj")
  else
    direct_deps+=("$dep_obj")
  fi
done < <(go list -m -json all 2>/dev/null | jq -c '.')

# Build final JSON structure with source metadata
deps_json=$(jq -n \
  --argjson direct "$(printf '%s\n' "${direct_deps[@]}" | jq -s '. // []')" \
  --argjson transitive "$(printf '%s\n' "${transitive_deps[@]}" | jq -s '. // []')" \
  '{
      direct: $direct,
      transitive: $transitive,
      source: {
        tool: "go mod",
        integration: "code"
      }
  }')

echo "$deps_json" | lunar collect -j ".lang.go.dependencies" -
