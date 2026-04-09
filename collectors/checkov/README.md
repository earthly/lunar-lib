# Checkov Collector

Auto-runs Checkov IaC security scanning on infrastructure code and detects existing Checkov CI executions.

## Overview

This collector runs Checkov against infrastructure code (Terraform, CloudFormation, Kubernetes manifests, Dockerfiles, ARM templates, etc.) and detects existing Checkov executions in CI pipelines. Scan results are normalized into the `.iac_scan` Component JSON category, feeding the `iac-scan` policy for IaC security enforcement. No configuration or secrets required.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.iac.files[]` | array | IaC files detected in the repository (signals IaC presence) |
| `.iac_scan.source` | object | Source metadata (tool, version, integration) |
| `.iac_scan.findings` | object | Finding counts by severity (critical, high, medium, low, total) |
| `.iac_scan.summary` | object | Summary booleans (has_critical, has_high, has_medium, has_low) |
| `.iac_scan.native.checkov.auto` | object | Raw Checkov scan results (auto-run) |
| `.iac_scan.native.checkov.cicd.cmds` | array | CI command metadata |

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `scan` | code | Auto-runs Checkov against repository infrastructure code |
| `cicd` | ci-after-command | Detects Checkov CLI executions in CI and collects report files |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/checkov@main
    on: ["domain:your-domain"]  # Or use tags
```

No configuration or secrets required. The `scan` sub-collector auto-runs Checkov using the `checkov-main` container image. The `cicd` sub-collector detects existing Checkov invocations in CI pipelines.

The `scan` collector detects IaC files before running Checkov and skips gracefully if none are found. Findings are capped at 100 per scan to avoid oversized Component JSON payloads.
