#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

if ! is_cpp_project; then
    echo "No C/C++ project detected" >&2
    exit 0
fi

direct_deps=()
cmake_packages=()

# Parse conanfile.txt [requires] section
if [[ -f "conanfile.txt" ]]; then
    in_requires=false
    while IFS= read -r line; do
        line=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

        if [[ "$line" == "[requires]" ]]; then
            in_requires=true
            continue
        fi
        if [[ "$line" == "["* ]]; then
            in_requires=false
            continue
        fi

        if $in_requires && [[ -n "$line" ]] && [[ "$line" != "#"* ]]; then
            pkg_version=$(echo "$line" | sed 's|[^/]*/||; s|@.*||')
            dep=$(jq -n --arg name "$line" --arg version "$pkg_version" --arg manager "conan" \
                '{name: $name, version: $version, manager: $manager}')
            direct_deps+=("$dep")
        fi
    done < conanfile.txt
fi

# Parse vcpkg.json dependencies
if [[ -f "vcpkg.json" ]]; then
    vcpkg_deps=$(jq -r '.dependencies[]? | if type == "string" then . else .name // empty end' vcpkg.json 2>/dev/null || true)
    while IFS= read -r dep_name; do
        if [[ -n "$dep_name" ]]; then
            dep=$(jq -n --arg name "$dep_name" --arg manager "vcpkg" \
                '{name: $name, manager: $manager}')
            direct_deps+=("$dep")
        fi
    done <<< "$vcpkg_deps"
fi

# Parse CMakeLists.txt for find_package() calls
if [[ -f "CMakeLists.txt" ]]; then
    packages=$(sed -n 's/.*find_package\s*(\s*\([A-Za-z0-9_]*\).*/\1/p' CMakeLists.txt | sort -u)
    while IFS= read -r pkg; do
        if [[ -n "$pkg" ]]; then
            cmake_packages+=("$pkg")
        fi
    done <<< "$packages"
fi

# Only collect if we found something
if [[ ${#direct_deps[@]} -eq 0 ]] && [[ ${#cmake_packages[@]} -eq 0 ]]; then
    exit 0
fi

# Build direct deps JSON array
if [[ ${#direct_deps[@]} -gt 0 ]]; then
    direct_json=$(printf '%s\n' "${direct_deps[@]}" | jq -s .)
else
    direct_json="[]"
fi

# Build cmake_packages JSON array
if [[ ${#cmake_packages[@]} -gt 0 ]]; then
    cmake_json=$(printf '%s\n' "${cmake_packages[@]}" | jq -R . | jq -s .)
else
    cmake_json="[]"
fi

jq -n \
    --argjson direct "$direct_json" \
    --argjson cmake_packages "$cmake_json" \
    '{
        direct: $direct,
        cmake_packages: $cmake_packages,
        source: { tool: "cpp", integration: "code" }
    }' | \
  lunar collect -j ".lang.cpp.dependencies" -
