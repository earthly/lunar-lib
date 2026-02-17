#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Check if this is a Node.js project
if ! is_nodejs_project; then
    echo "No Node.js project detected, exiting"
    exit 0
fi

package_json_exists=true
package_lock_exists=false
yarn_lock_exists=false
pnpm_lock_exists=false
tsconfig_exists=false
eslint_configured=false
prettier_configured=false
engines_node=""
monorepo_type=""

# Check lockfiles
if [[ -f "package-lock.json" ]]; then
    package_lock_exists=true
fi
if [[ -f "yarn.lock" ]]; then
    yarn_lock_exists=true
fi
if [[ -f "pnpm-lock.yaml" ]]; then
    pnpm_lock_exists=true
fi

# Check TypeScript
if compgen -G "tsconfig*.json" > /dev/null 2>&1; then
    tsconfig_exists=true
fi

# Check ESLint
if [[ -f ".eslintrc" ]] || [[ -f ".eslintrc.js" ]] || [[ -f ".eslintrc.cjs" ]] || \
   [[ -f ".eslintrc.yml" ]] || [[ -f ".eslintrc.yaml" ]] || [[ -f ".eslintrc.json" ]] || \
   compgen -G "eslint.config.*" > /dev/null 2>&1 || \
   jq -e '.eslintConfig' package.json > /dev/null 2>&1; then
    eslint_configured=true
fi

# Check Prettier
if [[ -f ".prettierrc" ]] || [[ -f ".prettierrc.js" ]] || [[ -f ".prettierrc.cjs" ]] || \
   [[ -f ".prettierrc.yml" ]] || [[ -f ".prettierrc.yaml" ]] || [[ -f ".prettierrc.json" ]] || \
   [[ -f ".prettierrc.toml" ]] || \
   compgen -G "prettier.config.*" > /dev/null 2>&1 || \
   jq -e '.prettier' package.json > /dev/null 2>&1; then
    prettier_configured=true
fi

# Extract engines.node from package.json
engines_node=$(jq -r '.engines.node // ""' package.json 2>/dev/null || echo "")

# Detect monorepo
if jq -e '.workspaces' package.json > /dev/null 2>&1; then
    monorepo_type="workspaces"
elif [[ -f "turbo.json" ]]; then
    monorepo_type="turborepo"
elif [[ -f "nx.json" ]]; then
    monorepo_type="nx"
elif [[ -f "lerna.json" ]]; then
    monorepo_type="lerna"
fi

# Determine build systems
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
if [[ ${#build_systems[@]} -eq 0 ]]; then
    build_systems=("npm")
fi

# Node.js version from the container
node_version=$(node -v 2>/dev/null | sed 's/^v//' || echo "")

# Build the JSON output
jq -n \
    --arg version "$node_version" \
    --argjson build_systems "$(printf '%s\n' "${build_systems[@]}" | jq -R . | jq -s .)" \
    --argjson package_json_exists "$package_json_exists" \
    --argjson package_lock_exists "$package_lock_exists" \
    --argjson yarn_lock_exists "$yarn_lock_exists" \
    --argjson pnpm_lock_exists "$pnpm_lock_exists" \
    --argjson tsconfig_exists "$tsconfig_exists" \
    --argjson eslint_configured "$eslint_configured" \
    --argjson prettier_configured "$prettier_configured" \
    --arg engines_node "$engines_node" \
    --arg monorepo_type "$monorepo_type" \
    '{
        build_systems: $build_systems,
        native: ({
            package_json: { exists: $package_json_exists },
            package_lock: { exists: $package_lock_exists },
            yarn_lock: { exists: $yarn_lock_exists },
            pnpm_lock: { exists: $pnpm_lock_exists },
            tsconfig: { exists: $tsconfig_exists },
            eslint_configured: $eslint_configured,
            prettier_configured: $prettier_configured,
            engines_node: (if $engines_node != "" then $engines_node else null end),
            monorepo: (if $monorepo_type != "" then {type: $monorepo_type} else null end)
        } | with_entries(select(.value != null))),
        source: {
            tool: "node",
            integration: "code"
        }
    }
    + (if $version != "" then {version: $version} else {} end)
    ' | lunar collect -j ".lang.nodejs" -
