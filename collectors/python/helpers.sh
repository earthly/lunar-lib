#!/bin/bash

# Shared helper functions for the python collector

# Check if the current directory is a Python project.
# Returns 0 (success) if it's a Python project, 1 (failure) otherwise.
is_python_project() {
    # Quick check: common Python project files
    if [[ -f "pyproject.toml" ]] || [[ -f "requirements.txt" ]] || [[ -f "setup.py" ]] || [[ -f "Pipfile" ]] || [[ -f "setup.cfg" ]]; then
        return 0
    fi
    # Fall back to checking for .py files (limit depth to avoid slow scans)
    if find . -maxdepth 3 -name "*.py" -type f -not -path './.git/*' 2>/dev/null | head -1 | grep -q .; then
        return 0
    fi
    return 1
}
