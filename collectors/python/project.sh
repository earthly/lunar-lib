#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Check if this is a Python project
if ! is_python_project; then
    echo "No Python project detected, exiting"
    exit 0
fi

# Detect key files
pyproject_exists=false
requirements_txt_exists=false
setup_py_exists=false
pipfile_exists=false
poetry_lock_exists=false
pipfile_lock_exists=false
python_version_file_exists=false

[[ -f "pyproject.toml" ]] && pyproject_exists=true
[[ -f "requirements.txt" ]] && requirements_txt_exists=true
[[ -f "setup.py" ]] && setup_py_exists=true
[[ -f "Pipfile" ]] && pipfile_exists=true
[[ -f "poetry.lock" ]] && poetry_lock_exists=true
[[ -f "Pipfile.lock" ]] && pipfile_lock_exists=true
[[ -f ".python-version" ]] && python_version_file_exists=true

# Detect build systems
build_systems=()
if [[ "$pyproject_exists" == true ]]; then
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
    # Check for uv (uv.lock or [tool.uv] in pyproject.toml)
    if grep -q "\[tool\.uv\]" pyproject.toml 2>/dev/null || [[ -f "uv.lock" ]]; then
        build_systems+=("uv")
    fi
fi
if [[ "$pipfile_exists" == true ]]; then
    build_systems+=("pipenv")
fi
if [[ "$setup_py_exists" == true ]] && ! printf '%s\n' "${build_systems[@]}" | grep -q "^setuptools$"; then
    build_systems+=("setuptools")
fi
if [[ "$requirements_txt_exists" == true ]]; then
    build_systems+=("pip")
fi
# Default if nothing detected
if [[ ${#build_systems[@]} -eq 0 ]]; then
    build_systems=("pip")
fi

# Detect linter
linter=""
if [[ -f ".ruff.toml" ]] || [[ -f "ruff.toml" ]]; then
    linter="ruff"
elif [[ "$pyproject_exists" == true ]] && grep -q "\[tool\.ruff\]" pyproject.toml 2>/dev/null; then
    linter="ruff"
elif [[ -f ".flake8" ]] || { [[ -f "setup.cfg" ]] && grep -q "\[flake8\]" setup.cfg 2>/dev/null; }; then
    linter="flake8"
elif [[ -f ".pylintrc" ]] || [[ -f "pylintrc" ]]; then
    linter="pylint"
elif [[ "$pyproject_exists" == true ]] && grep -q "\[tool\.pylint\]" pyproject.toml 2>/dev/null; then
    linter="pylint"
elif [[ "$pyproject_exists" == true ]] && grep -q "\[tool\.flake8\]" pyproject.toml 2>/dev/null; then
    linter="flake8"
fi

# Detect type checker
type_checker=""
if [[ -f "mypy.ini" ]] || [[ -f ".mypy.ini" ]]; then
    type_checker="mypy"
elif [[ "$pyproject_exists" == true ]] && grep -q "\[tool\.mypy\]" pyproject.toml 2>/dev/null; then
    type_checker="mypy"
elif [[ -f "pyrightconfig.json" ]]; then
    type_checker="pyright"
elif [[ "$pyproject_exists" == true ]] && grep -q "\[tool\.pyright\]" pyproject.toml 2>/dev/null; then
    type_checker="pyright"
fi

# Python version from container
python_version=$(python3 --version 2>/dev/null | awk '{print $2}' || echo "")

# Build and collect JSON
jq -n \
    --arg version "$python_version" \
    --argjson build_systems "$(printf '%s\n' "${build_systems[@]}" | jq -R . | jq -s .)" \
    --argjson pyproject "$pyproject_exists" \
    --argjson requirements_txt "$requirements_txt_exists" \
    --argjson setup_py "$setup_py_exists" \
    --argjson pipfile "$pipfile_exists" \
    --argjson poetry_lock "$poetry_lock_exists" \
    --argjson pipfile_lock "$pipfile_lock_exists" \
    --argjson python_version_file "$python_version_file_exists" \
    --arg linter "$linter" \
    --arg type_checker "$type_checker" \
    '{
        version: ($version | select(. != "")),
        build_systems: $build_systems,
        native: {
            pyproject: { exists: $pyproject },
            requirements_txt: { exists: $requirements_txt },
            setup_py: { exists: $setup_py },
            pipfile: { exists: $pipfile },
            poetry_lock: { exists: $poetry_lock },
            pipfile_lock: { exists: $pipfile_lock },
            python_version_file: { exists: $python_version_file },
            linter: (if $linter != "" then $linter else null end),
            type_checker: (if $type_checker != "" then $type_checker else null end)
        },
        source: {
            tool: "python",
            integration: "code"
        }
    }' | lunar collect -j ".lang.python" -
