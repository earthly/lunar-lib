#!/bin/bash
set -e

# Check if this is actually a Python project by looking for .py files
if ! find . -name "*.py" -type f 2>/dev/null | grep -q .; then
    echo "No Python files found, exiting"
    exit 0
fi

# Detect key files
pyproject_exists=false
requirements_exists=false
setup_py_exists=false
pipfile_exists=false

if [[ -f "pyproject.toml" ]]; then
  pyproject_exists=true
fi
if [[ -f "requirements.txt" ]]; then
  requirements_exists=true
fi
if [[ -f "setup.py" ]]; then
  setup_py_exists=true
fi
if [[ -f "Pipfile" ]]; then
  pipfile_exists=true
fi

# Detect build systems (can have multiple)
build_systems=()
if [[ "$pyproject_exists" == true ]]; then
  if grep -q "\[tool.poetry\]" pyproject.toml 2>/dev/null; then
    build_systems+=("poetry")
  fi
  if grep -q "\[build-system\]" pyproject.toml 2>/dev/null; then
    if grep -qi "hatch" pyproject.toml 2>/dev/null; then
      build_systems+=("hatch")
    fi
    if grep -qi "setuptools" pyproject.toml 2>/dev/null; then
      build_systems+=("setuptools")
    fi
  fi
fi
if [[ -f "Pipfile" ]]; then
  build_systems+=("pipenv")
fi
if [[ -f "setup.py" ]]; then
  build_systems+=("setuptools")
fi
if [[ -f "requirements.txt" ]]; then
  build_systems+=("pip")
fi
# Default to python if no build systems detected
if [[ ${#build_systems[@]} -eq 0 ]]; then
  build_systems=("python")
fi

# Python version
python_version=$(python3 --version 2>/dev/null | awk '{print $2}' || python --version 2>/dev/null | awk '{print $2}' || echo "")

# Emit structure
jq -n \
  --arg version "$python_version" \
  --argjson build_systems "$(printf '%s\n' "${build_systems[@]}" | jq -R . | jq -s .)" \
  --argjson pyproject_exists "$pyproject_exists" \
  --argjson requirements_exists "$requirements_exists" \
  --argjson setup_py_exists "$setup_py_exists" \
  --argjson pipfile_exists "$pipfile_exists" \
  '{
    version: $version,
    build_systems: $build_systems,
    native: {
      pyproject: { exists: $pyproject_exists },
      requirements_txt: { exists: $requirements_exists },
      setup_py: { exists: $setup_py_exists },
      pipfile: { exists: $pipfile_exists }
    }
  }' | lunar collect -j ".lang.python" -

