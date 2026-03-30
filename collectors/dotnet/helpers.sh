#!/bin/bash

# Shared helper functions for the dotnet collector

# Check if the current directory is a .NET project.
# Returns 0 (success) if it's a .NET project, 1 (failure) otherwise.
is_dotnet_project() {
    # Quick check: common .NET project/solution files in root
    if [[ -f "global.json" ]] || [[ -f "Directory.Build.props" ]]; then
        return 0
    fi
    for f in *.sln; do
        [[ -f "$f" ]] && return 0
    done
    # Check for project files anywhere (limit depth to avoid slow scans)
    if find . -maxdepth 3 \( -name "*.csproj" -o -name "*.fsproj" -o -name "*.vbproj" \) \
        -type f -not -path './.git/*' 2>/dev/null | head -1 | grep -q .; then
        return 0
    fi
    return 1
}
