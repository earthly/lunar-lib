#!/bin/bash
set -e

# Check if this is actually a Node.js project by looking for package.json
if [[ ! -f "package.json" ]]; then
    echo "No package.json found, exiting"
    exit 0
fi

package_json_exists=false
package_lock_exists=false
yarn_lock_exists=false
pnpm_lock_exists=false

if [[ -f "package.json" ]]; then
  package_json_exists=true
fi
if [[ -f "package-lock.json" ]]; then
  package_lock_exists=true
fi
if [[ -f "yarn.lock" ]]; then
  yarn_lock_exists=true
fi
if [[ -f "pnpm-lock.yaml" ]]; then
  pnpm_lock_exists=true
fi

# Determine build systems based on lock files (can have multiple)
build_systems=()
if [[ "$package_lock_exists" == true ]]; then
  build_systems+=("npm")
fi
if [[ "$yarn_lock_exists" == true ]]; then
  build_systems+=("yarn")
fi
if [[ "$pnpm_lock_exists" == true ]]; then
  build_systems+=("pnpm")
fi
# Default to npm if no lock files found
if [[ ${#build_systems[@]} -eq 0 ]]; then
  build_systems=("npm")
fi

# Node version
node_version=$(node -v 2>/dev/null | sed 's/^v//' || echo "")

jq -n \
  --arg version "$node_version" \
  --argjson build_systems "$(printf '%s\n' "${build_systems[@]}" | jq -R . | jq -s .)" \
  --argjson package_json_exists "$package_json_exists" \
  --argjson package_lock_exists "$package_lock_exists" \
  --argjson yarn_lock_exists "$yarn_lock_exists" \
  --argjson pnpm_lock_exists "$pnpm_lock_exists" \
  '{
    version: $version,
    build_systems: $build_systems,
    native: {
      package_json: { exists: $package_json_exists },
      package_lock: { exists: $package_lock_exists },
      yarn_lock: { exists: $yarn_lock_exists },
      pnpm_lock: { exists: $pnpm_lock_exists }
    }
  }' | lunar collect -j ".lang.nodejs" -

