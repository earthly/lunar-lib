#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Check if this is a Python project
if ! is_python_project; then
    echo "No Python project detected, exiting"
    exit 0
fi

# Detect build systems
build_systems=()
if [[ -f "pyproject.toml" ]]; then
    if grep -q "\[tool\.poetry\]" pyproject.toml 2>/dev/null; then
        build_systems+=("poetry")
    fi
    if grep -q "\[build-system\]" pyproject.toml 2>/dev/null; then
        if grep -qi "hatchling\|hatch" pyproject.toml 2>/dev/null; then
            build_systems+=("hatch")
        fi
        if grep -qi "setuptools" pyproject.toml 2>/dev/null; then
            build_systems+=("setuptools")
        fi
    fi
    if grep -q "\[tool\.uv\]" pyproject.toml 2>/dev/null || [[ -f "uv.lock" ]]; then
        build_systems+=("uv")
    fi
fi
if [[ -f "Pipfile" ]]; then
    build_systems+=("pipenv")
fi
if [[ -f "setup.py" ]] && ! printf '%s\n' "${build_systems[@]}" | grep -q "^setuptools$"; then
    build_systems+=("setuptools")
fi
if [[ -f "requirements.txt" ]]; then
    build_systems+=("pip")
fi
if [[ ${#build_systems[@]} -eq 0 ]]; then
    build_systems=("pip")
fi

# Detect linter
linter=""
if [[ -f ".ruff.toml" ]] || [[ -f "ruff.toml" ]]; then
    linter="ruff"
elif [[ -f "pyproject.toml" ]] && grep -q "\[tool\.ruff\]" pyproject.toml 2>/dev/null; then
    linter="ruff"
elif [[ -f ".flake8" ]] || { [[ -f "setup.cfg" ]] && grep -q "\[flake8\]" setup.cfg 2>/dev/null; }; then
    linter="flake8"
elif [[ -f ".pylintrc" ]] || [[ -f "pylintrc" ]]; then
    linter="pylint"
elif [[ -f "pyproject.toml" ]] && grep -q "\[tool\.pylint\]" pyproject.toml 2>/dev/null; then
    linter="pylint"
elif [[ -f "pyproject.toml" ]] && grep -q "\[tool\.flake8\]" pyproject.toml 2>/dev/null; then
    linter="flake8"
fi

# Detect type checker
type_checker=""
if [[ -f "mypy.ini" ]] || [[ -f ".mypy.ini" ]]; then
    type_checker="mypy"
elif [[ -f "pyproject.toml" ]] && grep -q "\[tool\.mypy\]" pyproject.toml 2>/dev/null; then
    type_checker="mypy"
elif [[ -f "pyrightconfig.json" ]]; then
    type_checker="pyright"
elif [[ -f "pyproject.toml" ]] && grep -q "\[tool\.pyright\]" pyproject.toml 2>/dev/null; then
    type_checker="pyright"
fi

# Python version from container
python_version=$(python3 --version 2>/dev/null | awk '{print $2}' || echo "")

# Build native object using jq — only include keys for files/tools that exist
# Start with empty object and conditionally add keys
native=$(jq -n '{}')
[[ -f "pyproject.toml" ]]  && native=$(echo "$native" | jq '. + {pyproject: {}}')
[[ -f "requirements.txt" ]] && native=$(echo "$native" | jq '. + {requirements_txt: {}}')
[[ -f "setup.py" ]]        && native=$(echo "$native" | jq '. + {setup_py: {}}')
[[ -f "Pipfile" ]]         && native=$(echo "$native" | jq '. + {pipfile: {}}')
[[ -f "poetry.lock" ]]     && native=$(echo "$native" | jq '. + {poetry_lock: {}}')
[[ -f "Pipfile.lock" ]]    && native=$(echo "$native" | jq '. + {pipfile_lock: {}}')
[[ -f ".python-version" ]] && native=$(echo "$native" | jq '. + {python_version_file: {}}')
[[ -n "$linter" ]]         && native=$(echo "$native" | jq --arg l "$linter" '. + {linter: $l}')
[[ -n "$type_checker" ]]   && native=$(echo "$native" | jq --arg t "$type_checker" '. + {type_checker: $t}')

jq -n \
    --arg version "$python_version" \
    --argjson build_systems "$(printf '%s\n' "${build_systems[@]}" | jq -R . | jq -s .)" \
    --argjson native "$native" \
    '{
        version: $version,
        build_systems: $build_systems,
        native: $native,
        source: {
            tool: "python",
            integration: "code"
        }
    } | if .version == "" then del(.version) else . end' | lunar collect -j ".lang.python" -
