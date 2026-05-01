# Git Collector

Collect git-ecosystem configuration data — pre-commit hooks today, with room for commitlint, gitattributes, gitmodules, and signed-commits as future sub-collectors.

## Overview

This collector parses repository-local git-ecosystem configuration into structured Component JSON. It is distinct from the `.vcs.*` namespace (hosted-VCS data: GitHub branch protection, PRs); `.git.*` is for the *local* git tool's config and the third-party tooling that hooks into it. The first sub-collector targets the [pre-commit framework](https://pre-commit.com): it parses `.pre-commit-config.yaml`, extracts the configured `repos[]` and their pinned `rev`s, and exposes flattened hook IDs plus the [pre-commit.ci](https://pre-commit.ci) `ci.skip` list. Data feeds the paired `git` policy.

## Collected Data

When no relevant config file is found for a sub-collector, this collector writes nothing under that key — object presence at `.git.<sub>` is itself the signal that the technology is configured. See [collector-reference.md § Write Nothing When Technology Not Detected](../../ai-context/collector-reference.md).

When a pre-commit config file is found, this collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.git.pre_commit.valid` | boolean | Whether the YAML config has valid syntax |
| `.git.pre_commit.path` | string | Path to the config file |
| `.git.pre_commit.repos[]` | array | Configured repos — each with `repo`, `rev`, and `hooks[]` (objects with `id`). Present when `valid: true` |
| `.git.pre_commit.hook_ids` | array | Flattened, deduplicated list of all configured hook IDs. Present when `valid: true` |
| `.git.pre_commit.hook_count` | number | Total number of hooks across all repos. Present when `valid: true` |
| `.git.pre_commit.repo_count` | number | Total number of `repos[]` entries. Present when `valid: true` |
| `.git.pre_commit.ci_skip` | array | Top-level `ci.skip` list — hook IDs disabled in pre-commit.ci. Empty array when not set. Present when `valid: true` |
| `.git.pre_commit.all_pinned` | boolean | `true` when every repo has a `rev` pinned to a non-floating ref (not `main`, `master`, `HEAD`, or empty). Present when `valid: true` |

## Collectors

| Collector | Description |
|-----------|-------------|
| `pre-commit` | Parses `.pre-commit-config.yaml` (or `.yml`) — first match wins |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/git@v1.0.0
    on: ["domain:your-domain"]
    # with:
    #   pre_commit_paths: ".pre-commit-config.yaml,.pre-commit-config.yml"
```
