# Git Collector

Collect git-ecosystem configuration data — pre-commit hooks, gitattributes, submodules, and recent commit-signature history.

## Overview

This collector parses repository-local git-ecosystem configuration into structured Component JSON. It is distinct from the `.vcs.*` namespace (hosted-VCS data: GitHub branch protection, PRs); `.git.*` is for the *local* git tool's config and the hooks/history it manages. The four sub-collectors target [pre-commit](https://pre-commit.com), `.gitattributes` (LFS / EOL / export-ignore rules), `.gitmodules` (submodule definitions), and recent commit-signature history (via `git log --pretty=format:'%G?'`). Data feeds the paired `git` policy.

## Collected Data

When no relevant config file is found for a sub-collector, this collector writes nothing under that key — object presence at `.git.<sub>` is itself the signal that the technology is configured. See [collector-reference.md § Write Nothing When Technology Not Detected](../../ai-context/collector-reference.md).

This collector writes to the following Component JSON paths (each rooted at `.git.<sub>`, present only when the sub-collector finds data):

| Path | Type | Description |
|------|------|-------------|
| `.git.pre_commit.valid` | boolean | Whether the YAML config has valid syntax |
| `.git.pre_commit.path` | string | Path to the config file |
| `.git.pre_commit.repos[]` | array | Configured repos — each with `repo`, `rev`, and `hooks[]` (objects with `id`) |
| `.git.pre_commit.hook_ids` | array | Flattened, deduplicated list of all configured hook IDs |
| `.git.pre_commit.hook_count` | number | Total number of hooks across all repos |
| `.git.pre_commit.repo_count` | number | Total number of `repos[]` entries |
| `.git.pre_commit.ci_skip` | array | Top-level `ci.skip` list — hook IDs disabled in pre-commit.ci |
| `.git.pre_commit.all_pinned` | boolean | `true` when every repo has a `rev` pinned to a non-floating ref |
| `.git.attributes.valid` | boolean | Whether the `.gitattributes` file parsed without errors |
| `.git.attributes.path` | string | Path to the `.gitattributes` file |
| `.git.attributes.rules_count` | number | Total number of non-comment, non-empty rules |
| `.git.attributes.lfs_patterns` | array | Patterns assigned `filter=lfs` |
| `.git.attributes.binary_patterns` | array | Patterns assigned the `binary` macro |
| `.git.attributes.eol_normalized` | boolean | `true` when at least one rule sets `text=auto` or equivalent |
| `.git.attributes.export_ignore_patterns` | array | Patterns assigned `export-ignore` |
| `.git.submodules.valid` | boolean | Whether `.gitmodules` parsed cleanly |
| `.git.submodules.path` | string | Path to the `.gitmodules` file |
| `.git.submodules.modules[]` | array | Per-submodule data (`name`, `path`, `url`, `branch`) |
| `.git.signing.default_branch` | string | Default branch the signature check ran against |
| `.git.signing.commits_examined` | number | Number of commits inspected from the default branch |
| `.git.signing.signature_counts` | object | Counts by `git log %G?` classification (`good`, `bad`, `unknown`, `unsigned`, `expired`, `revoked`) |

## Collectors

| Collector | Description |
|-----------|-------------|
| `pre-commit` | Parses `.pre-commit-config.yaml` (or `.yml`) — first match wins |
| `gitattributes` | Parses `.gitattributes` and classifies rules by attribute |
| `gitmodules` | Parses `.gitmodules` and extracts each submodule's `name`/`path`/`url`/`branch` |
| `signed-commits` | Inspects the last N commits on the default branch via `git log --pretty=format:'%G?'` |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/git@v1.0.0
    on: ["domain:your-domain"]
    # include: [pre-commit, signed-commits]  # Run a subset
    # with:
    #   pre_commit_paths: ".pre-commit-config.yaml,.pre-commit-config.yml"
    #   signed_commits_window: "100"
```
