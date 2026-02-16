# Python Collector

Collects Python project information, CI/CD commands, dependencies, and test coverage.

## Overview

This collector gathers metadata about Python projects including build tool detection, dependency lists, test coverage metrics, and CI/CD command tracking. It runs on both code changes (for static analysis of project structure) and CI hooks (to capture runtime metrics like test coverage and command versions).

**Note:** The CI-hook collectors (`test-coverage`, `cicd`) don't run tests—they observe and collect data from `pytest`/`python` commands that your CI pipeline already runs.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.lang.python` | object | Python project metadata (version, build systems, native file detection) |
| `.lang.python.cicd` | object | CI/CD command tracking with Python version |
| `.lang.python.tests` | object | Test coverage information |
| `.lang.python.dependencies` | object | Direct dependencies |
| `.testing.coverage` | object | Normalized cross-language coverage data |
| `.testing.source` | object | Test execution source metadata |

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `project` | code | Collects Python project structure (pyproject.toml, requirements.txt, lockfiles, linter config) |
| `dependencies` | code | Collects Python dependency list from requirements.txt or pyproject.toml |
| `cicd` | ci-before-command | Tracks Python/pip/poetry commands run in CI with version info |
| `test-coverage` | ci-after-command | Extracts coverage from coverage.xml after pytest runs |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/python@v1.0.0
    on: [python]  # Or use domain: ["domain:your-domain"]
    # include: [project, dependencies]  # Only include specific subcollectors
```
