# Grype Vulnerability Scanner Collector

Scans source code dependencies for known vulnerabilities using Grype.

## Overview

This collector runs [Grype](https://github.com/anchore/grype) — Anchore's open-source vulnerability scanner — against the repository to detect known CVEs in dependencies. It supports the ecosystems Grype covers (Go, Node.js, Python, Java, Rust, Ruby, PHP, .NET, and more) and writes normalized vulnerability data to `.sca` in the Component JSON, making results immediately consumable by the existing SCA policy. No secrets or vendor accounts are required. By default, Grype's vulnerability database is pre-baked into the collector image at build time, so CVE data is as current as the most recent image build; an experimental `db_auto_update` input can instead fetch the latest database at scan time.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.sca.source` | object | Source metadata (tool name, version, integration method) |
| `.sca.vulnerabilities` | object | Severity counts (critical, high, medium, low, total) |
| `.sca.findings[]` | array | Individual vulnerability findings with CVE, package, fix info |
| `.sca.summary` | object | Summary booleans (has_critical, has_high, all_fixable) |
| `.sca.native.grype` | object | Raw Grype match output and CI command detection data |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `auto` | code | Auto-scans the repository filesystem for dependency vulnerabilities |
| `cicd` | ci-after-command | Detects Grype executions in CI and captures command metadata |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/grype@main
    on: ["domain:your-domain"]
```

Zero configuration required. Works with any language Grype supports.

> **Note:** The `grype` collector writes to the same `.sca` paths as the `snyk` and `trivy` collectors. Use one SCA scanner per component, not several, or they will overwrite each other's `.sca` data.
