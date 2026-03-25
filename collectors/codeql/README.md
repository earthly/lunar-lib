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
| `.sast.findings` | object | Severity counts: `critical`, `high`, `medium`, `low`, `total` |
| `.sast.issues[]` | array | Individual findings with `severity`, `rule`, `file`, `line`, `message` |
| `.sast.summary` | object | `has_critical`, `has_high` booleans |
| `.sast.native.codeql.github_app` | object | Raw GitHub Code Scanning check-run data |
| `.sast.native.codeql.cicd` | object | CodeQL CLI invocations detected in CI |
| `.sast.native.codeql.sarif` | object | Raw SARIF output from CodeQL analysis (when available) |
| `.sast.running_in_prs` | boolean | Compliance proof that PRs are being scanned |

## Collectors

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `github-app` | code (PRs only) | Detects CodeQL via GitHub Code Scanning check-runs |
| `running-in-prs` | code (default branch) | Proves CodeQL is running on PRs (compliance proof for default branch) |
| `cicd` | ci-after-command | Detects `codeql` and legacy `codeql-runner` executions in CI, collects SARIF |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/codeql@main
    on: ["domain:your-domain"]
    secrets:
      GH_TOKEN: ${GH_TOKEN}
```

The `github-app` collector requires a `GH_TOKEN` secret for GitHub API access. CodeQL posts check-runs via the `github-advanced-security` app. The collector queries the check-runs API, filters by this app slug, and waits for completion.

The `cicd` collector matches both `codeql` and `codeql-runner` (legacy) binary executions in CI. When the traced command is `codeql database analyze` or `codeql database interpret-results` with a `--output=` flag, the collector reads the SARIF file from disk and collects it as raw data plus normalized findings counts and issues.

The `running-in-prs` collector queries the Lunar Hub database to verify PR scanning. It uses `lunar sql connection-string` to obtain database credentials. If unavailable, the collector skips silently.
