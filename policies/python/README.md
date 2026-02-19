# Python Project Guardrails

Enforce Python-specific project standards including lockfile presence, linter configuration, and Python version requirements.

## Overview

This policy validates Python projects against best practices for dependency management and project structure. It ensures projects have proper lockfiles for reproducible builds, a configured linter for code quality, and meet minimum Python version requirements in both the project and CI/CD environments.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `lockfile-exists` | Validates a lockfile exists | Missing dependency pinning |
| `linter-configured` | Ensures a linter is configured | No linter setup |
| `min-python-version` | Ensures minimum Python version | Python version too old |
| `min-python-version-cicd` | Ensures minimum Python version in CI/CD | CI/CD Python version too old |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.lang.python` | object | [`python`](https://github.com/earthly/lunar-lib/tree/main/collectors/python) collector |
| `.lang.python.poetry_lock_exists` | boolean | [`python`](https://github.com/earthly/lunar-lib/tree/main/collectors/python) collector |
| `.lang.python.pipfile_lock_exists` | boolean | [`python`](https://github.com/earthly/lunar-lib/tree/main/collectors/python) collector |
| `.lang.python.linter_configured` | boolean | [`python`](https://github.com/earthly/lunar-lib/tree/main/collectors/python) collector |
| `.lang.python.version` | string | [`python`](https://github.com/earthly/lunar-lib/tree/main/collectors/python) collector |
| `.lang.python.cicd.cmds` | array | [`python`](https://github.com/earthly/lunar-lib/tree/main/collectors/python) collector |

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/python@v1.0.0
    on: [python]  # Or use tags like ["domain:backend"]
    enforcement: report-pr
    # include: [lockfile-exists, linter-configured]  # Only run specific checks
    with:
      min_python_version: "3.9"       # Minimum Python version (default: "3.9")
      min_python_version_cicd: "3.9"  # Minimum CI/CD Python version (default: "3.9")
```

## Examples

### Passing Example

```json
{
  "lang": {
    "python": {
      "version": "3.12.1",
      "build_systems": ["poetry"],
      "pyproject_exists": true,
      "poetry_lock_exists": true,
      "linter_configured": true,
      "linter": "ruff",
      "type_checker_configured": true,
      "type_checker": "mypy"
    }
  }
}
```

### Failing Example

```json
{
  "lang": {
    "python": {
      "version": "3.8.5",
      "build_systems": ["pip"],
      "requirements_txt_exists": true,
      "poetry_lock_exists": false,
      "pipfile_lock_exists": false,
      "linter_configured": false
    }
  }
}
```

**Failure messages:**
- `"No dependency lockfile found. Use one of: poetry.lock, Pipfile.lock, or pin all versions in requirements.txt"`
- `"No Python linter configured. Set up one of: Ruff, Flake8, or Pylint"`
- `"Python version 3.8.5 is below minimum 3.9. Update to Python 3.9 or higher."`

## Remediation

### lockfile-exists
1. For Poetry projects: run `poetry lock` to generate `poetry.lock`
2. For Pipenv projects: run `pipenv lock` to generate `Pipfile.lock`
3. For pip projects: pin all versions in `requirements.txt` (e.g., `flask==3.0.0`)

### linter-configured
1. **Ruff (recommended):** Add `[tool.ruff]` to `pyproject.toml` or create `.ruff.toml`
2. **Flake8:** Create `.flake8` or add `[flake8]` to `setup.cfg`
3. **Pylint:** Create `.pylintrc`

### min-python-version
1. Update your project to use a newer Python version
2. Update `python_requires` in `setup.py` or `pyproject.toml`
3. Update your `.python-version` file (if using pyenv)

### min-python-version-cicd
1. Update your CI/CD pipeline to use a newer Python version
2. For GitHub Actions: update `python-version` in your workflow
3. For Docker-based builds: update your base Python image version
