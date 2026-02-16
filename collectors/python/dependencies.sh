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
    # Use Python's tomllib to parse dependencies from pyproject.toml
    pyproject_deps=$(python3 -c '
import sys
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        sys.exit(0)

with open("pyproject.toml", "rb") as f:
    data = tomllib.load(f)

# Check [project.dependencies]
project_deps = data.get("project", {}).get("dependencies", [])
for dep in project_deps:
    # Parse PEP 508 dependency specifier: "name>=version" or "name==version" etc.
    import re
    m = re.match(r"^([A-Za-z0-9_.-]+)\s*(?:[><=!~]+\s*(.+?))?(?:;.*)?$", dep.strip())
    if m:
        name = m.group(1)
        version = m.group(2) or ""
        # Clean trailing specifiers (e.g. ">=3.0,<4" -> "3.0")
        version = version.split(",")[0].strip() if version else ""
        print(f"{name}=={version}" if version else name)

# Check [tool.poetry.dependencies]
poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
if poetry_deps and not project_deps:
    for name, spec in poetry_deps.items():
        if name.lower() == "python":
            continue
        version = ""
        if isinstance(spec, str):
            version = spec.lstrip("^~>=<!")
        elif isinstance(spec, dict):
            version = spec.get("version", "").lstrip("^~>=<!")
        print(f"{name}=={version}" if version else name)
' 2>/dev/null || true)

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
                '{path: $path, version: ($version | select(. != "")), indirect: false}')")
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
            '{path: $path, version: ($version | select(. != "")), indirect: false}')")
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
            version=$(echo "$line" | grep -oP '"\K[^"]+' | head -1 || echo "")
            [[ "$version" == "*" ]] && version=""
            deps+=("$(jq -n --arg path "$name" --arg version "$version" \
                '{path: $path, version: ($version | select(. != "")), indirect: false}')")
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
