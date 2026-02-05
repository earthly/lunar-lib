# Semgrep Collector

Detects Semgrep security scans and collects findings data from GitHub App or CLI integrations.

## Overview

This collector detects Semgrep security scanning via GitHub App or CLI integration. It automatically categorizes results as SAST (for Semgrep Code analysis) or SCA (for Semgrep Supply Chain) and writes to the appropriate normalized Component JSON paths.

The collector auto-detects the scan type based on the check name (for GitHub App) or command flags (for CLI). Scans containing "supply chain", "supply-chain", or "sca" are categorized as SCA; all others default to SAST.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.sast.source` | object | Source metadata for SAST scans |
| `.sast.native.semgrep` | object | Raw Semgrep Code scan results |
| `.sca.source` | object | Source metadata for SCA scans |
| `.sca.native.semgrep` | object | Raw Semgrep Supply Chain scan results |

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `github-app` | code (PRs only) | Detects Semgrep GitHub App scans on pull requests |
| `github-app-default-branch` | code (default branch) | Checks if Semgrep has run on recent PRs (proof for default branch) |
| `cli` | ci-after-command | Detects Semgrep CLI executions in CI pipelines |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/semgrep@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [backend, python]
```

The `github-app` collector requires a `GH_TOKEN` secret for GitHub API access. The `github-app-default-branch` collector uses `lunar sql connection-string` to query the Lunar Hub database (no additional secrets required).
