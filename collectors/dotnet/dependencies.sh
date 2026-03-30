#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Check if this is a .NET project
if ! is_dotnet_project; then
    echo "No .NET project detected, exiting" >&2
    exit 0
fi

# Initialize arrays for dependencies and project references
direct_deps=()
project_refs=()

# Find and parse all project files
while IFS= read -r -d '' proj_file; do
    if [[ ! -f "$proj_file" ]]; then
        continue
    fi

    # Extract PackageReference dependencies
    while IFS= read -r line; do
        # Extract package name and version from PackageReference
        pkg_name=$(echo "$line" | sed -n 's/.*Include="\([^"]*\).*/\1/p' | head -n1)
        pkg_version=$(echo "$line" | sed -n 's/.*Version="\([^"]*\).*/\1/p' | head -n1)

        if [[ -n "$pkg_name" ]]; then
            # Build JSON object for this dependency
            dep_json=$(jq -n \
                --arg name "$pkg_name" \
                --arg version "$pkg_version" \
                '{
                    name: $name,
                    type: "package"
                }
                | if $version != "" then .version = $version else . end')
            direct_deps+=("$dep_json")
        fi
    done < <(grep -i 'PackageReference.*Include=' "$proj_file" 2>/dev/null || true)

    # Extract ProjectReference dependencies
    while IFS= read -r line; do
        proj_path=$(echo "$line" | sed -n 's/.*Include="\([^"]*\).*/\1/p' | head -n1)
        if [[ -n "$proj_path" ]]; then
            proj_ref_json=$(jq -n --arg path "$proj_path" '{ path: $path }')
            project_refs+=("$proj_ref_json")
        fi
    done < <(grep -i 'ProjectReference.*Include=' "$proj_file" 2>/dev/null || true)

done < <(find . -maxdepth 3 \( -name "*.csproj" -o -name "*.fsproj" -o -name "*.vbproj" \) -type f -print0 2>/dev/null || true)

# Only output if we found dependencies or project references
if [[ ${#direct_deps[@]} -gt 0 ]] || [[ ${#project_refs[@]} -gt 0 ]]; then
    jq -n \
        --argjson direct "$(printf '%s\n' "${direct_deps[@]}" | jq -s '.' 2>/dev/null || echo '[]')" \
        --argjson project_references "$(printf '%s\n' "${project_refs[@]}" | jq -s '.' 2>/dev/null || echo '[]')" \
        '{
            direct: $direct,
            project_references: $project_references,
            source: {
                tool: "dotnet",
                integration: "code"
            }
        }' | lunar collect -j ".lang.dotnet.dependencies" -
fi