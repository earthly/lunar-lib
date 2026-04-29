# Pre-commit Collector

Parses `.pre-commit-config.yaml` to collect configured hooks, their source repos, pinned revisions, and the optional `ci.skip` override list.

## Overview

This collector scans the repository for a [pre-commit framework](https://pre-commit.com) configuration file at `.pre-commit-config.yaml` (or `.yml` variant). It parses the YAML to extract each `repos[]` entry (with `repo`, `rev`, and `hooks[]`), produces a flattened list of hook IDs for easy policy assertions, and captures the top-level `ci.skip` list used by [pre-commit.ci](https://pre-commit.ci) to disable hooks in the hosted CI service. Data feeds the paired `pre-commit` policy.

## Collected Data

When no pre-commit config file is found, this collector writes nothing — object presence at `.code_quality.pre_commit` is itself the signal that pre-commit is configured. See [collector-reference.md § Write Nothing When Technology Not Detected](../../ai-context/collector-reference.md).

When a config file is found, this collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.code_quality.pre_commit.valid` | boolean | Whether the YAML config has valid syntax |
| `.code_quality.pre_commit.path` | string | Path to the config file |
| `.code_quality.pre_commit.repos[]` | array | Configured repos — each with `repo`, `rev`, and `hooks[]` (objects with `id`). Present when `valid: true` |
| `.code_quality.pre_commit.hook_ids` | array | Flattened, deduplicated list of all configured hook IDs. Present when `valid: true` |
| `.code_quality.pre_commit.hook_count` | number | Total number of hooks across all repos. Present when `valid: true` |
| `.code_quality.pre_commit.repo_count` | number | Total number of `repos[]` entries. Present when `valid: true` |
| `.code_quality.pre_commit.ci_skip` | array | Top-level `ci.skip` list — hook IDs disabled in pre-commit.ci. Empty array when not set. Present when `valid: true` |
| `.code_quality.pre_commit.all_pinned` | boolean | `true` when every repo has a `rev` pinned to a non-floating ref (not `main`, `master`, `HEAD`, or empty). Present when `valid: true` |

> **Schema note:** `.code_quality.*` is currently used by tool-agnostic code quality scanners (e.g. SonarQube quality gate, coverage, issue counts). Pre-commit data lives alongside that as `code_quality.pre_commit` rather than overlapping with the tool-agnostic fields. See the spec PR description for the layering discussion.

## Collectors

| Collector | Description |
|-----------|-------------|
| `config` | Parses `.pre-commit-config.yaml` (or `.yml`) — first match wins |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/pre-commit@v1.0.0
    on: ["domain:your-domain"]
    # with:
    #   paths: ".pre-commit-config.yaml,.pre-commit-config.yml"
```
