# Trivy Vulnerability Scanner Collector

Scans source code dependencies for known vulnerabilities using Trivy.

## Overview

This collector runs Trivy filesystem scans against repository source code to detect known CVEs in dependencies. It supports all ecosystems Trivy covers (Go, Node.js, Python, Java, Rust, Ruby, PHP, .NET, etc.) and writes normalized vulnerability data to `.sca` in the Component JSON, making results immediately consumable by the existing SCA policy.

No secrets or vendor accounts are required — Trivy's vulnerability database is bundled in the Docker image.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.sca.source` | object | Source metadata (tool name, version, integration method) |
| `.sca.vulnerabilities` | object | Severity counts (critical, high, medium, low, total) |
| `.sca.findings[]` | array | Individual vulnerability findings with CVE, package, fix info |
| `.sca.summary` | object | Summary booleans (has_critical, has_high, all_fixable) |

## Collectors

This integration provides the following collectors:

| Collector | Description |
|-----------|-------------|
| `scan` | Scans the repository filesystem for dependency vulnerabilities |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/trivy@main
    on: ["domain:your-domain"]
```

Zero configuration required. Works with any language Trivy supports.

> **Note:** If you already use the `snyk` collector, the `trivy` collector will overwrite `.sca` data since both write to the same paths. Use one SCA scanner per component, not both.
