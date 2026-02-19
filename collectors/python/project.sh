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
if [[ ${#build_systems[@]} -eq 0 ]]; then
    build_systems=("pip")
fi

# Detect linter
linter_configured=false
linter=""
if [[ -f ".ruff.toml" ]] || [[ -f "ruff.toml" ]]; then
    linter="ruff"; linter_configured=true
elif [[ "$pyproject_exists" == true ]] && grep -q "\[tool\.ruff\]" pyproject.toml 2>/dev/null; then
    linter="ruff"; linter_configured=true
elif [[ -f ".flake8" ]] || { [[ -f "setup.cfg" ]] && grep -q "\[flake8\]" setup.cfg 2>/dev/null; }; then
    linter="flake8"; linter_configured=true
elif [[ -f ".pylintrc" ]] || [[ -f "pylintrc" ]]; then
    linter="pylint"; linter_configured=true
elif [[ "$pyproject_exists" == true ]] && grep -q "\[tool\.pylint\]" pyproject.toml 2>/dev/null; then
    linter="pylint"; linter_configured=true
elif [[ "$pyproject_exists" == true ]] && grep -q "\[tool\.flake8\]" pyproject.toml 2>/dev/null; then
    linter="flake8"; linter_configured=true
fi

# Detect type checker
type_checker_configured=false
type_checker=""
if [[ -f "mypy.ini" ]] || [[ -f ".mypy.ini" ]]; then
    type_checker="mypy"; type_checker_configured=true
elif [[ "$pyproject_exists" == true ]] && grep -q "\[tool\.mypy\]" pyproject.toml 2>/dev/null; then
    type_checker="mypy"; type_checker_configured=true
elif [[ -f "pyrightconfig.json" ]]; then
    type_checker="pyright"; type_checker_configured=true
elif [[ "$pyproject_exists" == true ]] && grep -q "\[tool\.pyright\]" pyproject.toml 2>/dev/null; then
    type_checker="pyright"; type_checker_configured=true
fi

# Python version from container
python_version=$(python3 --version 2>/dev/null | awk '{print $2}' || echo "")

# Build and collect — flat booleans at .lang.python level (matching Java pattern)
jq -n \
    --arg version "$python_version" \
    --argjson build_systems "$(printf '%s\n' "${build_systems[@]}" | jq -R . | jq -s .)" \
    --argjson pyproject_exists "$pyproject_exists" \
    --argjson requirements_txt_exists "$requirements_txt_exists" \
    --argjson setup_py_exists "$setup_py_exists" \
    --argjson pipfile_exists "$pipfile_exists" \
    --argjson poetry_lock_exists "$poetry_lock_exists" \
    --argjson pipfile_lock_exists "$pipfile_lock_exists" \
    --argjson python_version_file_exists "$python_version_file_exists" \
    --argjson linter_configured "$linter_configured" \
    --arg linter "$linter" \
    --argjson type_checker_configured "$type_checker_configured" \
    --arg type_checker "$type_checker" \
    '{
        build_systems: $build_systems,
        pyproject_exists: $pyproject_exists,
        requirements_txt_exists: $requirements_txt_exists,
        setup_py_exists: $setup_py_exists,
        pipfile_exists: $pipfile_exists,
        poetry_lock_exists: $poetry_lock_exists,
        pipfile_lock_exists: $pipfile_lock_exists,
        python_version_file_exists: $python_version_file_exists,
        linter_configured: $linter_configured,
        linter: (if $linter != "" then $linter else null end),
        type_checker_configured: $type_checker_configured,
        type_checker: (if $type_checker != "" then $type_checker else null end),
        source: {
            tool: "python",
            integration: "code"
        }
    } | if $version != "" then .version = $version else . end' | lunar collect -j ".lang.python" -
