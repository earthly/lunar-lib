#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

if ! is_cpp_project; then
    echo "No C/C++ project detected" >&2
    exit 0
fi

# Detect build systems
bs_list=()
cmake_exists=false
makefile_exists=false
conanfile_exists=false
vcpkg_json_exists=false
meson_build_exists=false

if [[ -f "CMakeLists.txt" ]]; then
    cmake_exists=true
    bs_list+=("cmake")
fi

if [[ -f "Makefile" ]] || [[ -f "makefile" ]] || [[ -f "GNUmakefile" ]]; then
    makefile_exists=true
    bs_list+=("make")
fi

if [[ -f "meson.build" ]]; then
    meson_build_exists=true
    bs_list+=("meson")
fi

if [[ -f "configure.ac" ]] || [[ -f "configure.in" ]]; then
    bs_list+=("autotools")
fi

# Bazel: only count if C/C++ source files exist alongside it
if [[ -f "BUILD" ]] || [[ -f "BUILD.bazel" ]] || [[ -f "WORKSPACE" ]] || [[ -f "WORKSPACE.bazel" ]]; then
    if find . -maxdepth 3 -type f \( -name "*.c" -o -name "*.cpp" -o -name "*.cc" -o -name "*.cxx" \) -not -path './.git/*' 2>/dev/null | head -1 | grep -q .; then
        bs_list+=("bazel")
    fi
fi

if [[ -f "conanfile.txt" ]] || [[ -f "conanfile.py" ]]; then
    conanfile_exists=true
fi

if [[ -f "vcpkg.json" ]]; then
    vcpkg_json_exists=true
fi

# Build build_systems JSON array
if [[ ${#bs_list[@]} -gt 0 ]]; then
    build_systems=$(printf '%s\n' "${bs_list[@]}" | jq -R . | jq -s .)
else
    build_systems="[]"
fi

# Extract C++ standard from CMakeLists.txt
cpp_standard=""
if [[ -f "CMakeLists.txt" ]]; then
    cpp_standard=$(sed -n 's/.*[Ss][Ee][Tt]\s*(\s*CMAKE_CXX_STANDARD\s\+\([0-9]\+\).*/\1/p' CMakeLists.txt | head -1)
    if [[ -z "$cpp_standard" ]]; then
        cpp_standard=$(sed -n 's/.*-std=c++\([0-9]\+\).*/\1/p' CMakeLists.txt | head -1)
    fi
fi

# Fallback: check Makefiles for -std=c++XX
if [[ -z "$cpp_standard" ]]; then
    for mf in Makefile makefile GNUmakefile; do
        if [[ -f "$mf" ]]; then
            cpp_standard=$(sed -n 's/.*-std=c++\([0-9]\+\).*/\1/p' "$mf" | head -1)
            if [[ -n "$cpp_standard" ]]; then break; fi
        fi
    done
fi

# Fallback: check meson.build
if [[ -z "$cpp_standard" ]] && [[ -f "meson.build" ]]; then
    cpp_standard=$(sed -n "s/.*'cpp_std',\s*'c++\([0-9]\+\)'.*/\1/p" meson.build | head -1)
fi

# Count source files
c_count=$(find . -maxdepth 10 -type f -name "*.c" -not -path './.git/*' 2>/dev/null | wc -l)
cpp_count=$(find . -maxdepth 10 -type f \( -name "*.cpp" -o -name "*.cc" -o -name "*.cxx" \) -not -path './.git/*' 2>/dev/null | wc -l)
header_count=$(find . -maxdepth 10 -type f \( -name "*.h" -o -name "*.hpp" -o -name "*.hh" -o -name "*.hxx" \) -not -path './.git/*' 2>/dev/null | wc -l)

# Build and collect JSON
jq -n \
    --argjson build_systems "$build_systems" \
    --argjson cmake_exists "$cmake_exists" \
    --argjson makefile_exists "$makefile_exists" \
    --argjson conanfile_exists "$conanfile_exists" \
    --argjson vcpkg_json_exists "$vcpkg_json_exists" \
    --argjson meson_build_exists "$meson_build_exists" \
    --arg cpp_standard "$cpp_standard" \
    --argjson c_count "$c_count" \
    --argjson cpp_count "$cpp_count" \
    --argjson header_count "$header_count" \
    '{
        build_systems: $build_systems,
        cmake_exists: $cmake_exists,
        makefile_exists: $makefile_exists,
        conanfile_exists: $conanfile_exists,
        vcpkg_json_exists: $vcpkg_json_exists,
        meson_build_exists: $meson_build_exists,
        source_files: {
            c: $c_count,
            cpp: $cpp_count,
            headers: $header_count
        },
        source: { tool: "cpp", integration: "code" }
    }
    | if $cpp_standard != "" then .cpp_standard = $cpp_standard else . end' | \
  lunar collect -j ".lang.cpp" -
