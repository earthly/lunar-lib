#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Check if this is a Python project
if ! is_python_project; then
    echo "No Python project detected, exiting"
    exit 0
fi

deps=()
source_tool="pip"

# Try pyproject.toml first (richer metadata)
if [[ -f "pyproject.toml" ]]; then
    pyproject_deps=$(python3 "$(dirname "$0")/parse_pyproject.py" 2>/dev/null || true)

    if [[ -n "$pyproject_deps" ]]; then
        # Check if it's a poetry project
        if grep -q "\[tool\.poetry\]" pyproject.toml 2>/dev/null; then
            source_tool="poetry"
        fi
        while IFS= read -r line; do
            [[ -z "$line" ]] && continue
            name="$line"
            version=""
            if [[ "$line" == *"=="* ]]; then
                name="${line%%==*}"
                version="${line#*==}"
            fi
            deps+=("$(jq -n --arg path "$name" --arg version "$version" \
                'if $version != "" then {path: $path, version: $version, indirect: false}
                 else {path: $path, indirect: false} end')")
        done <<< "$pyproject_deps"
    fi
fi

# Fall back to requirements.txt if no deps from pyproject.toml
if [[ ${#deps[@]} -eq 0 ]] && [[ -f "requirements.txt" ]]; then
    source_tool="pip"
    while IFS= read -r line; do
        # Strip comments and whitespace
        clean=$(echo "$line" | sed 's/#.*//' | tr -d '[:space:]')
        [[ -z "$clean" ]] && continue
        # Skip -r, -e, --index-url and other flags
        [[ "$clean" == -* ]] && continue

        name="$clean"
        version=""
        if [[ "$clean" == *"=="* ]]; then
            name="${clean%%==*}"
            version="${clean#*==}"
        elif [[ "$clean" == *">="* ]]; then
            name="${clean%%>=*}"
            version="${clean#*>=}"
            version="${version%%,*}"
        fi
        deps+=("$(jq -n --arg path "$name" --arg version "$version" \
            'if $version != "" then {path: $path, version: $version, indirect: false}
             else {path: $path, indirect: false} end')")
    done < requirements.txt
fi

# Fall back to Pipfile
if [[ ${#deps[@]} -eq 0 ]] && [[ -f "Pipfile" ]]; then
    source_tool="pipenv"
    # Simple Pipfile parser: extract [packages] section
    in_packages=false
    while IFS= read -r line; do
        if [[ "$line" == "[packages]" ]]; then
            in_packages=true
            continue
        fi
        if [[ "$line" == "["* ]]; then
            in_packages=false
            continue
        fi
        if [[ "$in_packages" == true ]] && [[ -n "$line" ]]; then
            name=$(echo "$line" | cut -d= -f1 | tr -d '[:space:]')
            [[ -z "$name" ]] && continue
            version=$(echo "$line" | sed -n 's/.*"\([^"]*\)".*/\1/p' | head -1)
            [[ "$version" == "*" ]] && version=""
            deps+=("$(jq -n --arg path "$name" --arg version "$version" \
                'if $version != "" then {path: $path, version: $version, indirect: false}
                 else {path: $path, indirect: false} end')")
        fi
    done < Pipfile
fi

# Only collect if we found dependencies
if [[ ${#deps[@]} -gt 0 ]]; then
    jq -n \
        --argjson direct "$(printf '%s\n' "${deps[@]}" | jq -s '.')" \
        --arg tool "$source_tool" \
        '{
            direct: $direct,
            transitive: [],
            source: {
                tool: $tool,
                integration: "code"
            }
        }' | lunar collect -j ".lang.python.dependencies" -
else
    echo "No dependencies found"
fi
