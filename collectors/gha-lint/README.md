# GHA Workflow Lint Collector

Parses GitHub Actions workflows, runs actionlint, and detects version pinning status for supply-chain hygiene.

## Overview

This collector analyzes all GitHub Actions workflow files (`.github/workflows/*.yml`) in a repository. It extracts structured data from each workflow (name, triggers, jobs, action references), runs [actionlint](https://github.com/rhysd/actionlint) for syntax and type checking, and classifies version pinning status for every action reference. The result is a comprehensive view of GHA workflow quality and supply-chain hygiene.

Skips gracefully if no `.github/workflows/` directory exists.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.ci.gha.source` | object | Source metadata (tool, version, integration) |
| `.ci.gha.workflows[]` | array | Parsed workflow data (file, name, triggers, jobs, permissions, actions) |
| `.ci.gha.actionlint` | object | Lint results (errors with file/line/rule, error and warning counts) |
| `.ci.gha.pinning_summary` | object | Aggregate pinning stats (SHA, tag, branch, unpinned counts) |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `workflows` | Parses workflows, runs actionlint, and detects version pinning |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/gha-lint@main
    on: ["domain:your-domain"]  # Or use tags like [backend, frontend]
```
