# Snyk Collector

Detects Snyk security scans and collects vulnerability data from GitHub App or CLI integrations.

## Overview

This collector detects Snyk security scanning across multiple integration methods (GitHub App, CLI) and automatically categorizes results based on scan type. It writes normalized data to the appropriate Component JSON category depending on which Snyk product was used:

- **Snyk Open Source** → `.sca` (default, or `snyk test` command)
- **Snyk Code** → `.sast` (context contains "code", or `snyk code` command)
- **Snyk Container** → `.container_scan` (context contains "container", or `snyk container` command)
- **Snyk IaC** → `.iac_scan` (context contains "iac" or "infrastructure", or `snyk iac` command)

## Collected Data

This collector writes to the following Component JSON paths based on scan type:

| Path | Type | Description |
|------|------|-------------|
| `.sca.source` | object | Source metadata when Snyk Open Source scan detected |
| `.sca.native.snyk` | object | Raw Snyk results for SCA scans |
| `.sca.native.snyk.running_in_prs` | boolean | Proves Snyk is scanning PRs (set on default branch) |
| `.sast.source` | object | Source metadata when Snyk Code scan detected |
| `.sast.native.snyk` | object | Raw Snyk results for SAST scans |
| `.container_scan.source` | object | Source metadata when Snyk Container scan detected |
| `.container_scan.native.snyk` | object | Raw Snyk results for container scans |
| `.iac_scan.source` | object | Source metadata when Snyk IaC scan detected |
| `.iac_scan.native.snyk` | object | Raw Snyk results for IaC scans |

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `github-app` | code (PRs only) | Detects Snyk GitHub App scans on pull requests |
| `running-in-prs` | code (default branch) | Proves Snyk is running on PRs (compliance proof for default branch) |
| `cli` | ci-after-command | Detects Snyk CLI executions in CI pipelines |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/snyk@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [backend, go]
```

## Secrets

| Secret | Required | Used By | Description |
|--------|----------|---------|-------------|
| `GH_TOKEN` | Yes | github-app | GitHub token for API access to query commit statuses |
| `PG_PASSWORD` | No | running-in-prs | Database password (uses `lunar sql connection-string` if not set) |
| `PG_USER` | No | running-in-prs | Database user (defaults to `api3` if not set) |

The `cli` collector does not require any secrets.

Configure secrets in your `lunar-config.yml`:

```yaml
secrets:
  GH_TOKEN:
    from_env: GITHUB_TOKEN
  # Optional: only needed if lunar sql connection-string is not available
  PG_PASSWORD:
    from_env: LUNAR_DB_PASSWORD
```
