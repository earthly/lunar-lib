# Gitleaks Collector

Detects hardcoded secrets using Gitleaks — either by auto-running scans or by collecting results from existing Gitleaks CI executions.

## Overview

This collector has two modes of operation:

1. **Auto-scan** (`scan` sub-collector): Runs Gitleaks against the repository source code on every collection cycle. Detects API keys, passwords, tokens, and other credentials. Results are written to the normalized `.secrets` Component JSON category.

2. **CI detection** (`cicd` sub-collector): Detects existing Gitleaks executions in CI pipelines. Captures command and version metadata. When `--report-path` / `-r` is found in the traced command, collects the report file and normalizes findings into `.secrets.cicd`.

Both modes feed into the `secrets` policy for enforcement.

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
