# Semgrep Collector

Detects Semgrep security scans and collects findings data from GitHub App or CLI integrations.

## Overview

This collector detects Semgrep security scanning via GitHub App or CLI integration. It automatically categorizes results as SAST (for Semgrep Code analysis) or SCA (for Semgrep Supply Chain) and writes to the appropriate normalized Component JSON paths.

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
| `github-app-main` | code (default branch) | Checks if Semgrep has run on recent PRs (proof for main branch) |
| `cli` | ci-after-command | Detects Semgrep CLI executions in CI pipelines |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/semgrep@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [backend, python]
```

## Required Secrets

| Secret | Required | Description |
|--------|----------|-------------|
| `GH_TOKEN` | Yes | GitHub token for API access (checking check-runs) |
| `PG_PASSWORD` | No | Database password for main branch queries |

## Category Detection

The collector automatically categorizes Semgrep scans:

| Semgrep Product | Detection | Category |
|-----------------|-----------|----------|
| Semgrep Code | Check name doesn't contain "supply chain" or "sca" | `.sast` |
| Semgrep Supply Chain | Check name contains "supply chain", "supply-chain", or "sca" | `.sca` |
| CLI with `--supply-chain` | Command contains `--supply-chain` | `.sca` |
| CLI (default) | Any other semgrep CLI command | `.sast` |
