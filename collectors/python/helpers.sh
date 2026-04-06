#!/bin/bash

# Shared helper functions for the python collector

# Check if the repo contains a Python project (root or subdirs).
# Requires a Python project manifest — stray .py files alone are not sufficient,
# since the collector reports on build systems, dependency managers, and tooling
# that only exist when a manifest is present.
is_python_project() {
    [[ -f "pyproject.toml" ]] || [[ -f "requirements.txt" ]] || [[ -f "setup.py" ]] || [[ -f "Pipfile" ]] || [[ -f "setup.cfg" ]] && return 0
    git ls-files '**/pyproject.toml' '**/requirements.txt' '**/setup.py' '**/Pipfile' '**/setup.cfg' 2>/dev/null | head -1 | grep -q .
}
