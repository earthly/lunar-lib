#!/bin/bash

is_cpp_project() {
    # Build system files
    if [[ -f "CMakeLists.txt" ]]; then return 0; fi
    if [[ -f "Makefile" ]] || [[ -f "makefile" ]] || [[ -f "GNUmakefile" ]]; then return 0; fi
    if [[ -f "meson.build" ]]; then return 0; fi
    if [[ -f "configure.ac" ]] || [[ -f "configure.in" ]]; then return 0; fi
    if [[ -f "conanfile.txt" ]] || [[ -f "conanfile.py" ]]; then return 0; fi
    if [[ -f "vcpkg.json" ]]; then return 0; fi

    # Bazel with C/C++ source files
    if [[ -f "BUILD" ]] || [[ -f "BUILD.bazel" ]] || [[ -f "WORKSPACE" ]] || [[ -f "WORKSPACE.bazel" ]]; then
        if find . -maxdepth 3 -type f \( -name "*.c" -o -name "*.cpp" -o -name "*.cc" -o -name "*.cxx" \) -not -path './.git/*' 2>/dev/null | head -1 | grep -q .; then
            return 0
        fi
    fi

    # Fallback: C/C++ source files
    if find . -maxdepth 3 -type f \( -name "*.c" -o -name "*.cpp" -o -name "*.cc" -o -name "*.cxx" \) -not -path './.git/*' 2>/dev/null | head -1 | grep -q .; then
        return 0
    fi

    return 1
}
