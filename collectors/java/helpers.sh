#!/bin/bash

# Shared helper functions for the java collector

# Check if the current directory is a Java project.
# Returns 0 (success) if it's a Java project, 1 (failure) otherwise.
is_java_project() {
    # Quick check: if pom.xml or build.gradle exists, it's a Java project
    if [[ -f "pom.xml" ]] || [[ -f "build.gradle" ]] || [[ -f "build.gradle.kts" ]]; then
        return 0
    fi
    # Fall back to checking for .java files (limit depth to avoid slow scans)
    if find . -maxdepth 3 -name "*.java" -type f -not -path './.git/*' 2>/dev/null | head -1 | grep -q .; then
        return 0
    fi
    return 1
}
