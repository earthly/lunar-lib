# Gitleaks Collector

Automatically scans repositories for hardcoded secrets using Gitleaks.

## Overview

This collector auto-runs Gitleaks secret scanning on every repository. It detects API keys, passwords, tokens, and other credentials in code. Results are written to the normalized `.secrets` Component JSON category, enabling the `secrets` policy to enforce secret-free codebases.

The collector also detects Gitleaks executions in CI pipelines, capturing command and version metadata. When `--report-path` / `-r` is found in the CI command, the report file is collected and normalized into `.secrets.cicd`.

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

No configuration or secrets required. The `scan` collector runs Gitleaks automatically using the `gitleaks-main` container image. The `ci` collector detects Gitleaks invocations in CI pipelines.

The `scan` collector uses `--no-git` mode to scan the working directory without requiring git history. Findings are limited to 50 per scan to avoid oversized Component JSON payloads.

The `cicd` collector parses `--report-path` / `-r` from the traced command to locate and collect the Gitleaks JSON report file, similar to the syft CI collector pattern.
