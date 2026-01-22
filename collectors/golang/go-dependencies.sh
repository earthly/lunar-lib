#!/bin/bash

set -e

# Collect Go module dependencies into .lang.go.deps

# Check if this is actually a Go project by looking for .go files
if ! find . -name "*.go" -type f 2>/dev/null | grep -q .; then
    echo "No Go files found, exiting"
    exit 0
fi

# Ensure all modules are downloaded
go mod download >/dev/null 2>&1 || true

# Helper function to get license for a module
get_license() {
  local module_path="$1"
  local module_version="$2"
  
  # Build module@version string for go list
  local module_spec="$module_path"
  if [[ -n "$module_version" ]] && [[ "$module_version" != "" ]] && [[ "$module_version" != "none" ]]; then
    module_spec="${module_path}@${module_version}"
    # Ensure module is downloaded
    go mod download "$module_spec" >/dev/null 2>&1 || true
  fi
  
  # Try to get module directory from go list (this should work for cached modules)
  local module_dir=$(go list -m -f '{{.Dir}}' "$module_spec" 2>/dev/null || echo "")
  
  # If go list doesn't work, try module cache directly
  if [[ -z "$module_dir" ]] || [[ ! -d "$module_dir" ]]; then
    local gomodcache="${GOMODCACHE:-${GOPATH:-$HOME/go}/pkg/mod}"
    if [[ -n "$module_version" ]] && [[ "$module_version" != "" ]] && [[ "$module_version" != "none" ]]; then
      # Module cache uses lowercase paths with @version
      local cache_path=$(echo "$module_path" | tr '[:upper:]' '[:lower:]')
      module_dir="$gomodcache/${cache_path}@${module_version}"
    fi
  fi
  
  if [[ -z "$module_dir" ]] || [[ ! -d "$module_dir" ]]; then
    echo ""
    return
  fi
  
  # Check for common LICENSE file names (including versioned and hyphenated variants)
  for license_file in "LICENSE" "LICENSE.txt" "LICENSE.md" "LICENCE" "LICENCE.txt" "LICENCE.md" \
                      "LICENSE-MIT" "LICENSE-MIT.txt" "LICENSE-APACHE" "LICENSE-APACHE.txt" \
                      "LICENSE-BSD" "LICENSE-BSD.txt" "LICENSE-GPL" "LICENSE-GPL.txt" \
                      "LICENSE-ISC" "LICENSE-ISC.txt" "LICENSE-MPL" "LICENSE-MPL.txt"; do
    if [[ -f "$module_dir/$license_file" ]]; then
      # Strategy 1: Check file name patterns (some repos use LICENSE-MIT.txt etc)
      if echo "$license_file" | grep -qiE "(MIT|Apache|BSD|GPL|LGPL|Mozilla|MPL|ISC)"; then
        local name_license=$(echo "$license_file" | grep -oiE "(MIT|Apache|BSD|GPL|LGPL|Mozilla|MPL|ISC)" | head -n 1)
        if [[ -n "$name_license" ]]; then
          echo "$name_license"
          return
        fi
      fi
      
      # Strategy 2: Look for license in go.mod file (some modules specify it there)
      if [[ -f "$module_dir/go.mod" ]]; then
        local mod_license=$(grep -iE "^(license|licence)" "$module_dir/go.mod" 2>/dev/null | \
          grep -oiE "(MIT|Apache|BSD|GPL|LGPL|Mozilla|MPL|ISC)" | \
          head -n 1 || echo "")
        if [[ -n "$mod_license" ]]; then
          echo "$mod_license"
          return
        fi
      fi
      
      # Strategy 3: Look for license name patterns in first 50 lines
      # Try multiple patterns: start of line, "License:" prefix, "under the X license", etc.
      local license_text=$(head -n 50 "$module_dir/$license_file" 2>/dev/null | \
        grep -iE "^(MIT|Apache|BSD|GPL|LGPL|Mozilla|MPL|ISC|ISC License|MIT License|Apache License|BSD License|GNU General Public|GNU Lesser)" | \
        grep -oiE "(MIT|Apache|BSD|GPL|LGPL|Mozilla|MPL|ISC)" | \
        head -n 1 || \
        head -n 50 "$module_dir/$license_file" 2>/dev/null | \
        grep -iE "(License|Licence)[\s:]+(MIT|Apache|BSD|GPL|LGPL|Mozilla|MPL|ISC)" | \
        grep -oiE "(MIT|Apache|BSD|GPL|LGPL|Mozilla|MPL|ISC)" | \
        head -n 1 || \
        head -n 50 "$module_dir/$license_file" 2>/dev/null | \
        grep -iE "(under the|licensed under|released under|distributed under).*(MIT|Apache|BSD|GPL|LGPL|Mozilla|MPL|ISC)" | \
        grep -oiE "(MIT|Apache|BSD|GPL|LGPL|Mozilla|MPL|ISC)" | \
        head -n 1 || \
        head -n 50 "$module_dir/$license_file" 2>/dev/null | \
        grep -iE "(MIT|Apache|BSD|GPL|LGPL|Mozilla|MPL|ISC).*(License|Licence)" | \
        grep -oiE "(MIT|Apache|BSD|GPL|LGPL|Mozilla|MPL|ISC)" | \
        head -n 1 || echo "")
      
      if [[ -n "$license_text" ]]; then
        echo "$license_text"
        return
      fi
      
      # Strategy 4: Check for common license text patterns (extract just the name)
      # Scan more of the file (first 200 lines) and look for license names in various contexts
      local file_content=$(head -n 200 "$module_dir/$license_file" 2>/dev/null)
      # Look for license names that appear as standalone words or in common phrases
      # Use word boundaries to avoid false matches, but also check for common variations
      
      # MIT variations (including detection by characteristic text)
      if echo "$file_content" | grep -qiE "\bMIT\b|\bMIT License\b|\bMassachusetts Institute of Technology\b|Permission is hereby granted, free of charge"; then
        echo "MIT"
        return
      # Apache variations (check Apache before Apache2 to avoid partial match)
      elif echo "$file_content" | grep -qiE "\bApache License\b|\bApache Software License\b|\bApache-2\.0\b|\bASL\b"; then
        echo "Apache"
        return
      # BSD variations (including detection by characteristic text)
      elif echo "$file_content" | grep -qiE "\bBSD License\b|\bBerkeley Software Distribution\b|\bBSD-3-Clause\b|\bBSD-2-Clause\b|\b3-Clause BSD\b|\b2-Clause BSD\b|Redistribution and use in source and binary forms"; then
        echo "BSD"
        return
      # GPL variations (check GPL before LGPL to avoid partial match)
      elif echo "$file_content" | grep -qiE "\bGPL\b|\bGNU General Public License\b|\bGPLv2\b|\bGPLv3\b|\bGPL-2\b|\bGPL-3\b"; then
        echo "GPL"
        return
      # LGPL variations
      elif echo "$file_content" | grep -qiE "\bLGPL\b|\bGNU Lesser General Public License\b|\bLGPLv2\b|\bLGPLv3\b|\bLGPL-2\b|\bLGPL-3\b"; then
        echo "LGPL"
        return
      # Mozilla/MPL variations
      elif echo "$file_content" | grep -qiE "\bMozilla Public License\b|\bMPL\b|\bMPL-2\.0\b|\bMozilla\b"; then
        echo "Mozilla"
        return
      # ISC variations
      elif echo "$file_content" | grep -qiE "\bISC License\b|\bISC\b"; then
        echo "ISC"
        return
      fi
    fi
  done
  
  # Also check for replaced modules - they might have licenses in the replacement location
  if [[ -n "$module_version" ]] && [[ "$module_version" != "none" ]]; then
    local replace_info=$(go list -m -f '{{.Replace}}' "$module_spec" 2>/dev/null || echo "")
    if [[ -n "$replace_info" ]] && [[ "$replace_info" != "<nil>" ]]; then
      # Try to get license from replacement module
      local replace_path=$(go list -m -f '{{.Replace.Path}}' "$module_spec" 2>/dev/null || echo "")
      local replace_version=$(go list -m -f '{{.Replace.Version}}' "$module_spec" 2>/dev/null || echo "")
      if [[ -n "$replace_path" ]]; then
        local replace_license=$(get_license "$replace_path" "$replace_version")
        if [[ -n "$replace_license" ]]; then
          echo "$replace_license"
          return
        fi
      fi
    fi
  fi
  
  echo ""
}

# Process modules and build JSON with license info
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
  
  # Get license (pass both path and version)
  license=$(get_license "$path" "$version")
  
  # Build dependency object
  dep_obj=$(jq -n \
    --arg path "$path" \
    --arg version "$version" \
    --argjson indirect "$indirect" \
    --arg license "$license" \
    --argjson replace "$replace" \
    '{
      path: $path,
      version: $version,
      indirect: $indirect,
      license: $license,
      replace: (if $replace then {path: $replace.Path, version: ($replace.Version // "")} else null end)
    }')
  
  if [[ "$indirect" == "true" ]]; then
    transitive_deps+=("$dep_obj")
  else
    direct_deps+=("$dep_obj")
  fi
done < <(go list -m -json all 2>/dev/null | jq -c '.')

# Build final JSON structure
deps_json=$(jq -n \
  --argjson direct "$(printf '%s\n' "${direct_deps[@]}" | jq -s '.')" \
  --argjson transitive "$(printf '%s\n' "${transitive_deps[@]}" | jq -s '.')" \
  '{
      direct: $direct,
      transitive: $transitive
  }')

echo "$deps_json" | lunar collect -j ".lang.go.dependencies" -

