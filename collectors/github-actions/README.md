# GitHub Actions Collector

Parses GitHub Actions workflows, runs actionlint, detects version pinning, and analyzes security misconfigurations.

## Overview

This collector analyzes all GitHub Actions workflow files (`.github/workflows/*.yml`) in a repository. It extracts structured data from each workflow (name, triggers, jobs, action references), runs [actionlint](https://github.com/rhysd/actionlint) for syntax and type checking, classifies version pinning status for every action reference, and performs security analysis for injection risks, permissions issues, and credential hygiene. Skips gracefully if no `.github/workflows/` directory exists.

## Collected Data

This collector writes to **normalized** (vendor-agnostic), **security**, and **native** (GHA-specific) Component JSON paths:

### Normalized paths

| Path | Type | Description |
|------|------|-------------|
| `.ci.lint` | object | CI config lint results (errors with file/line/rule, counts) |
| `.ci.dependencies` | object | CI dependency pinning status (total, pinned, unpinned, item details) |

### Security paths

| Path | Type | Description |
|------|------|-------------|
| `.ci.security.source` | object | Tool metadata (`tool`, `version`, `integration`) |
| `.ci.security.injectable_expressions[]` | array | `${{ }}` expressions in `run:` blocks and `actions/github-script` `script:` fields using attacker-controllable contexts |
| `.ci.security.dangerous_checkouts[]` | array | `pull_request_target` workflows that check out PR head code |
| `.ci.security.permissions_missing[]` | array | Workflows with no explicit `permissions:` key |
| `.ci.security.write_all_permissions[]` | array | Workflows or jobs with `permissions: write-all` |
| `.ci.security.persist_credentials[]` | array | `actions/checkout` steps without `persist-credentials: false` |
| `.ci.security.secrets_inherit[]` | array | Reusable workflow calls using `secrets: inherit` |

### Native paths

| Path | Type | Description |
|------|------|-------------|
| `.ci.native.github_actions` | object | Raw GHA workflow data (full parsed workflows with triggers, jobs, permissions, action refs) |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `workflows` | Parses workflows, runs actionlint, and detects version pinning |
| `security` | Analyzes workflows for injection risks, permission issues, and insecure patterns |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/github-actions@main
    on: ["domain:your-domain"]  # Or use tags like [backend, frontend]
```
