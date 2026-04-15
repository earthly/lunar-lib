# CodeRabbit Collector

Detect CodeRabbit AI code review activity and configuration across repositories.

## Overview

This collector detects CodeRabbit usage on pull requests by querying GitHub check-runs for the `coderabbitai` app, and discovers CodeRabbit configuration files in the repository. It writes to the normalized `ai.code_reviewers[]` array for tool-agnostic policy checks, and stores CodeRabbit-specific data in `ai.native.coderabbit`.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.ai.code_reviewers[]` | array entry | Normalized code reviewer entry: tool name, check name, detection status, last seen timestamp |
| `.ai.native.coderabbit.config_file` | string | Path to the CodeRabbit config file (`.coderabbit.yaml` or `.coderabbit.yml`) |
| `.ai.native.coderabbit.config_exists` | boolean | Whether a CodeRabbit config file exists in the repository |

## Collectors

This integration provides the following collectors:

| Collector | Hook | Description |
|-----------|------|-------------|
| `code-reviewer` | `code` (PRs only) | Detects CodeRabbit check-runs on PRs via GitHub API |
| `config` | `code` | Discovers `.coderabbit.yaml` / `.coderabbit.yml` config files |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/coderabbit@main
    on: ["domain:your-domain"]
    secrets:
      GH_TOKEN: "${{ secrets.GH_TOKEN }}"
```

