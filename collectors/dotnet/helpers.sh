#!/bin/bash

# Shared helper functions for the dotnet collector

# Check if the current directory is a .NET project.
# Returns 0 (success) if it's a .NET project, 1 (failure) otherwise.
is_dotnet_project() {
    # Quick check: common .NET project indicators
    if find . -maxdepth 3 -name "*.csproj" -o -name "*.fsproj" -o -name "*.vbproj" 2>/dev/null | head -1 | grep -q .; then
        return 0
    fi
    if [[ -f "global.json" ]] || [[ -f "Directory.Build.props" ]]; then
        return 0
    fi
    if find . -maxdepth 3 -name "*.sln" -type f 2>/dev/null | head -1 | grep -q .; then
        return 0
    fi
    return 1
}
