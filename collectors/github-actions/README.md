# GitHub Actions Collector

Parses GitHub Actions workflows, runs actionlint, and detects version pinning status for supply-chain hygiene.

## Overview

This collector analyzes all GitHub Actions workflow files (`.github/workflows/*.yml`) in a repository. It extracts structured data from each workflow (name, triggers, jobs, steps, action references), runs [actionlint](https://github.com/rhysd/actionlint) for syntax and type checking, and classifies version pinning status for every action reference. The native data includes full step-level details (run blocks, with parameters, env vars) for downstream policy analysis. Skips gracefully if no `.github/workflows/` directory exists.

## Collected Data

This collector writes to **normalized** (vendor-agnostic) and **native** (GHA-specific) Component JSON paths:

### Normalized paths

| Path | Type | Description |
|------|------|-------------|
| `.ci.lint` | object | CI config lint results (errors with file/line/rule, counts) |
| `.ci.dependencies` | object | CI dependency pinning status (total, pinned, unpinned, item details) |

### Native paths

| Path | Type | Description |
|------|------|-------------|
| `.ci.native.github_actions.workflows[]` | array | Full parsed workflows with triggers, jobs, steps, permissions, action refs, run blocks, with parameters |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `workflows` | Parses workflows, runs actionlint, and detects version pinning |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/github-actions@main
    on: ["domain:your-domain"]  # Or use tags like [backend, frontend]
```
