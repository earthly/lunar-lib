# Gitleaks Collector

Detects hardcoded secrets using Gitleaks — either by auto-running scans or by collecting results from existing Gitleaks CI executions.

## Overview

This collector detects hardcoded secrets using Gitleaks in two modes: the `scan` sub-collector auto-runs Gitleaks on every repo, while the `cicd` sub-collector detects existing Gitleaks executions in CI and collects their report files. Results are normalized into the `.secrets` Component JSON category for the `secrets` policy.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.secrets.source` | object | Source metadata (tool, version, integration) |
| `.secrets.issues[]` | array | Normalized findings with rule, file, line, type (empty = clean) |
| `.secrets.cicd[]` | array | Normalized findings from CI report (when report file found) |
| `.secrets.native.gitleaks.auto` | object | Raw Gitleaks report (auto-scan) |
| `.secrets.native.gitleaks.cicd.cmds` | array | CI command metadata |
| `.secrets.native.gitleaks.cicd.report` | array | Raw CI report (when report file found) |

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `scan` | code | Auto-runs Gitleaks against repository source code |
| `cicd` | ci-after-command | Detects Gitleaks CLI executions in CI and collects report file |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/gitleaks@main
    on: ["domain:your-domain"]  # Or use tags
```

No configuration or secrets required. The `scan` sub-collector runs Gitleaks automatically using the `gitleaks-main` container image. The `cicd` sub-collector detects existing Gitleaks invocations in CI pipelines and collects their report files.

The `scan` collector uses `--no-git` mode to scan the working directory without requiring git history. Findings are limited to 50 per scan to avoid oversized Component JSON payloads.

The `cicd` collector parses `--report-path` / `-r` from the traced command to locate and collect the Gitleaks JSON report file, similar to the syft CI collector pattern.
