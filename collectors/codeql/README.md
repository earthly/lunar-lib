# CodeQL Collector

Detects GitHub CodeQL security scans and collects scan metadata from GitHub Code Scanning or CLI integrations.

## Overview

This collector detects CodeQL static analysis via GitHub's Code Scanning integration or CLI usage in CI pipelines. CodeQL is GitHub's semantic code analysis engine — unlike pattern-matching tools, it compiles source code into a relational database and queries it for vulnerabilities using inter-procedural data flow analysis.

All data is written to the `.sast` category, enabling tool-agnostic SAST policies that work across CodeQL, Semgrep, Snyk Code, and other SAST tools.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.sast.source` | object | Source metadata (`tool`, `integration`, optional `version`) |
| `.sast.native.codeql.github_app` | object | Raw GitHub Code Scanning check-run data |
| `.sast.native.codeql.cicd` | object | CodeQL CLI invocations detected in CI |
| `.sast.running_in_prs` | boolean | Compliance proof that PRs are being scanned |

## Collectors

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `github-app` | code (PRs only) | Detects CodeQL via GitHub Code Scanning check-runs |
| `running-in-prs` | code (default branch) | Proves CodeQL is running on PRs (compliance proof for default branch) |
| `cli` | ci-after-command | Detects `codeql` CLI executions in CI pipelines |
| `cli-legacy` | ci-after-command | Detects legacy `codeql-runner` executions in CI pipelines |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/codeql@main
    on: ["domain:your-domain"]
    secrets:
      GH_TOKEN: ${GH_TOKEN}
```

The `github-app` collector requires a `GH_TOKEN` secret for GitHub API access. CodeQL runs as part of GitHub Code Scanning, which posts check-runs via the `github-code-scanning` app. The collector queries the check-runs API, filters by this app slug, and waits for completion.

The `cli` and `cli-legacy` collectors match `codeql` and `codeql-runner` binary executions in CI, used by teams running analysis outside of GitHub Actions.

The `running-in-prs` collector queries the Lunar Hub database to verify PR scanning. It uses `lunar sql connection-string` to obtain database credentials. If unavailable, the collector skips silently.
