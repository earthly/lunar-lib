#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Check if this is a .NET project
if ! is_dotnet_project; then
    echo "No .NET project detected, exiting" >&2
    exit 0
fi

# Initialize variables
sdk_version=""
global_json_exists=false
directory_build_props_exists=false
packages_lock_exists=false
project_files=()
solution_files=()
test_projects=()
target_frameworks=()

# Check for global.json and extract SDK version
if [[ -f "global.json" ]]; then
    global_json_exists=true
    # Extract SDK version using grep/sed (no jq dependency for CI collectors)
    sdk_version=$(grep -A5 '"sdk"' global.json 2>/dev/null | grep '"version"' | sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1 || true)
fi

# Check for Directory.Build.props
if [[ -f "Directory.Build.props" ]]; then
    directory_build_props_exists=true
fi

# Check for any packages.lock.json files
if find . -name "packages.lock.json" -type f 2>/dev/null | head -1 | grep -q .; then
    packages_lock_exists=true
fi

# Find solution files
while IFS= read -r -d '' file; do
    solution_files+=("$file")
done < <(find . -maxdepth 3 -name "*.sln" -type f -print0 2>/dev/null || true)

# Find project files and analyze them
while IFS= read -r -d '' proj_file; do
    # Determine project type from extension
    case "$proj_file" in
        *.csproj) proj_type="csharp" ;;
        *.fsproj) proj_type="fsharp" ;;
        *.vbproj) proj_type="vbnet" ;;
        *) continue ;;
    esac

    # Extract target framework from project file
    target_framework=""
    output_type=""

    # Look for TargetFramework or TargetFrameworks
    if [[ -f "$proj_file" ]]; then
        target_framework=$(grep -o '<TargetFramework[^>]*>[^<]*</TargetFramework>' "$proj_file" 2>/dev/null | sed 's/<[^>]*>//g' | head -n1 || true)
        if [[ -z "$target_framework" ]]; then
            # Try TargetFrameworks (plural) and take the first one
            target_framework=$(grep -o '<TargetFrameworks[^>]*>[^<]*</TargetFrameworks>' "$proj_file" 2>/dev/null | sed 's/<[^>]*>//g' | sed 's/;.*//' | head -n1 || true)
        fi

        # Extract OutputType
        output_type=$(grep -o '<OutputType[^>]*>[^<]*</OutputType>' "$proj_file" 2>/dev/null | sed 's/<[^>]*>//g' | head -n1 || true)

        # Check if it's a test project by looking for test framework packages
        is_test_project=false
        test_framework=""
        if grep -q 'Microsoft\.NET\.Test\.Sdk\|xunit\|NUnit\|MSTest' "$proj_file" 2>/dev/null; then
            is_test_project=true
            if grep -q 'xunit' "$proj_file" 2>/dev/null; then
                test_framework="xunit"
            elif grep -q 'NUnit' "$proj_file" 2>/dev/null; then
                test_framework="nunit"
            elif grep -q 'MSTest' "$proj_file" 2>/dev/null; then
                test_framework="mstest"
            else
                test_framework="unknown"
            fi
        fi
    fi

    # Add to target frameworks list (avoid duplicates)
    if [[ -n "$target_framework" ]]; then
        if ! printf '%s\n' "${target_frameworks[@]}" | grep -Fxq "$target_framework"; then
            target_frameworks+=("$target_framework")
        fi
    fi

    # Build project info JSON object
    proj_json=$(jq -n \
        --arg path "$proj_file" \
        --arg type "$proj_type" \
        --arg target_framework "$target_framework" \
        --arg output_type "$output_type" \
        '{
            path: $path,
            type: $type
        }
        | if $target_framework != "" then .target_framework = $target_framework else . end
        | if $output_type != "" then .output_type = $output_type else . end')

    project_files+=("$proj_json")

    # Add to test projects if it's a test project
    if [[ "$is_test_project" == true ]]; then
        test_proj_json=$(jq -n \
            --arg path "$proj_file" \
            --arg type "$proj_type" \
            --arg test_framework "$test_framework" \
            '{
                path: $path,
                type: $type,
                test_framework: $test_framework
            }')
        test_projects+=("$test_proj_json")
    fi
done < <(find . -maxdepth 3 \( -name "*.csproj" -o -name "*.fsproj" -o -name "*.vbproj" \) -type f -print0 2>/dev/null || true)

# Build and output the complete JSON
jq -n \
    --arg sdk_version "$sdk_version" \
    --argjson global_json_exists "$global_json_exists" \
    --argjson directory_build_props_exists "$directory_build_props_exists" \
    --argjson packages_lock_exists "$packages_lock_exists" \
    --argjson project_files "$(printf '%s\n' "${project_files[@]}" | jq -s '.' 2>/dev/null || echo '[]')" \
    --argjson solution_files "$(printf '%s\n' "${solution_files[@]}" | jq -R . | jq -s '.' 2>/dev/null || echo '[]')" \
    --argjson test_projects "$(printf '%s\n' "${test_projects[@]}" | jq -s '.' 2>/dev/null || echo '[]')" \
    --argjson target_frameworks "$(printf '%s\n' "${target_frameworks[@]}" | jq -R . | jq -s '.' 2>/dev/null || echo '[]')" \
    '{
        global_json_exists: $global_json_exists,
        directory_build_props_exists: $directory_build_props_exists,
        packages_lock_exists: $packages_lock_exists,
        project_files: $project_files,
        solution_files: $solution_files,
        test_projects: $test_projects,
        target_frameworks: $target_frameworks,
        source: {
            tool: "dotnet",
            integration: "code"
        }
    }
    | if $sdk_version != "" then .sdk_version = $sdk_version else . end' | lunar collect -j ".lang.dotnet" -