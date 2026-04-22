#!/bin/bash
# Parses Helm charts: metadata, helm lint, dependencies, values schema presence.
set -e

# Function to process a single Chart.yaml file
process_chart() {
    local chart_file="$1"
    local chart_dir
    chart_dir=$(dirname "$chart_file")
    local rel_dir="${chart_dir#./}"

    # Parse Chart.yaml fields
    local name version app_version
    name=$(yq -r '.name // ""' "$chart_file" 2>/dev/null)
    version=$(yq -r '.version // ""' "$chart_file" 2>/dev/null)
    app_version=$(yq -r '.appVersion // ""' "$chart_file" 2>/dev/null)

    # Detect strict semver (X.Y.Z[-pre][+build])
    local version_is_semver=false
    if echo "$version" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$'; then
        version_is_semver=true
    fi

    # Run helm lint
    local lint_output lint_passed lint_errors
    local lint_args=("$chart_dir")
    if [ "${LUNAR_VAR_LINT_STRICT:-false}" = "true" ]; then
        lint_args=(--strict "$chart_dir")
    fi
    set +e
    lint_output=$(helm lint "${lint_args[@]}" 2>&1)
    local lint_status=$?
    set -e
    if [ "$lint_status" -eq 0 ]; then
        lint_passed=true
        lint_errors='[]'
    else
        lint_passed=false
        lint_errors=$(echo "$lint_output" | grep -E '\[ERROR\]|Error:' | jq -R . | jq -s '.')
        if [ "$(echo "$lint_errors" | jq 'length')" = "0" ]; then
            # Fallback: include the full output as a single error so reviewers see why it failed.
            lint_errors=$(echo "$lint_output" | jq -Rs '[.]')
        fi
    fi

    # Check for values.schema.json
    local has_values_schema=false
    local schema_path=""
    if [ -f "$chart_dir/values.schema.json" ]; then
        has_values_schema=true
        schema_path="${rel_dir}/values.schema.json"
    fi

    # Extract dependencies (from Chart.yaml `dependencies:` array)
    # is_pinned: true when version is set and not "*"
    local dependencies
    dependencies=$(yq -o=json '.dependencies // []' "$chart_file" 2>/dev/null | \
        jq '[.[] | {
            name: (.name // ""),
            version: (.version // ""),
            repository: (.repository // ""),
            is_pinned: ((.version // "") | length > 0 and . != "*")
        }]')

    # Build chart object
    local chart_obj
    chart_obj=$(jq -n \
        --arg path "$rel_dir" \
        --arg name "$name" \
        --arg version "$version" \
        --argjson version_is_semver "$version_is_semver" \
        --argjson lint_passed "$lint_passed" \
        --argjson lint_errors "$lint_errors" \
        --arg app_version "$app_version" \
        --argjson has_values_schema "$has_values_schema" \
        --arg schema_path "$schema_path" \
        --argjson dependencies "$dependencies" \
        '{
            path: $path,
            name: $name,
            version: $version,
            version_is_semver: $version_is_semver,
            lint_passed: $lint_passed,
            lint_errors: $lint_errors
        }
        + (if $app_version == "" then {} else {app_version: $app_version} end)
        + {has_values_schema: $has_values_schema}
        + (if $schema_path == "" then {} else {schema_path: $schema_path} end)
        + {dependencies: $dependencies}')

    echo "$chart_obj"
}

export -f process_chart

# Find Chart.yaml files using configured find command
FIND_CMD="${LUNAR_VAR_FIND_COMMAND:-find . -type f \( -name 'Chart.yaml' -o -name 'Chart.yml' \)}"

# Skip charts unpacked inside another chart's `charts/` dependency dir
# (path contains two `/charts/` segments, e.g. charts/api/charts/postgresql/Chart.yaml).
charts_output=$(eval "$FIND_CMD" 2>/dev/null | \
    grep -vE '/charts/[^/]+/charts/[^/]+/Chart\.ya?ml$' | \
    sort -u | \
    parallel -j 4 process_chart 2>/dev/null)

chart_count=$(printf '%s\n' "$charts_output" | grep -c '^{' || true)
if [ "$chart_count" -gt 0 ]; then
    while IFS= read -r chart_obj; do
        [ -z "$chart_obj" ] && continue
        printf '%s' "$chart_obj" | lunar collect -j --array-append ".k8s.helm.charts" -
    done <<< "$charts_output"

    HELM_VERSION=$(helm version --template='{{.Version}}' 2>/dev/null | sed 's/^v//' || echo "unknown")
    jq -n --arg tool "helm" --arg version "$HELM_VERSION" \
        '{tool: $tool, version: $version}' | lunar collect -j ".k8s.helm.source" -
fi
