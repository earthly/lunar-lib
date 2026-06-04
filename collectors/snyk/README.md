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
| `.sca.vulnerabilities` | object | Severity counts (`critical`/`high`/`medium`/`low`/`total`) — `snyk test` only |
| `.sca.findings` | array | Per-vulnerability detail (severity, package, version, CVE, fix version, fixable) |
| `.sca.summary` | object | `has_critical`/`has_high`/…/`all_fixable` booleans |
| `.sca.native.snyk.cicd.raw` | object | Raw `snyk test --json` output, verbatim |
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

### Capturing CLI vulnerability results

The `cli` collector hooks `ci-after-command`, which sees the command line and
exit code but **not** the scanner's stdout. To capture actual findings (the
`.sca.vulnerabilities` / `.findings` / `.summary` fields the SCA policy reads),
run `snyk test` with `--json-file-output`:

```yaml
- run: snyk test --severity-threshold=critical --json-file-output=snyk-sca.json
```

The collector parses the `--json-file-output` path out of the traced command,
reads that file, and normalizes it. Without the flag it still records the
command and version, but no findings — there's nothing on disk to read.

Normalization uses `jq`; `install.sh` fetches it into `$LUNAR_BIN_DIR` when
absent. If `jq` can't be installed the raw JSON is still captured under
`.sca.native.snyk.cicd.raw`; only the normalized counts are skipped.

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/snyk@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [backend, go]
```

Required secrets:
- `GH_TOKEN` — GitHub token for API access (required for github-app collector)
