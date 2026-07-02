# Grype Vulnerability Scanner Collector

Scans source code dependencies for known vulnerabilities using Grype.

## Overview

This collector runs [Grype](https://github.com/anchore/grype) — Anchore's open-source vulnerability scanner — against the repository to detect known CVEs in dependencies. It supports the ecosystems Grype covers (Go, Node.js, Python, Java, Rust, Ruby, PHP, .NET, and more) and writes normalized vulnerability data to `.sca` in the Component JSON, making results immediately consumable by the existing SCA policy. No secrets or vendor accounts are required. By default it scans against the vulnerability database baked into the collector image, so freshness tracks the image rebuild cadence; set `db_auto_update: true` — on a Hub that honors the `size: large` profile these collectors declare — to fetch the latest database at scan time and pick up CVEs published since the image was built.

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
| `rescan` | cron | Re-runs the `auto` scan on a schedule (daily by default) and overwrites `.sca` so the SCA policy re-evaluates against newly-published CVEs |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/grype@main
    on: ["domain:your-domain"]
```

Zero configuration required. Works with any language Grype supports.

By default this also enables the `rescan` cron sub-collector, which re-runs the
scan daily on each component's default branch and overwrites `.sca`. To keep the
on-push (`auto`) and CI-detection (`cicd`) scans but turn the scheduled re-scan
off, exclude it:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/grype@main
    on: ["domain:your-domain"]
    exclude: [rescan]
```

> **Note:** The `grype` collector writes to the same `.sca` paths as the `snyk` and `trivy` collectors. Use one SCA scanner per component, not several, or they will overwrite each other's `.sca` data.

> **Re-scan freshness:** By default (`db_auto_update: false`), each cron re-scan uses the DB baked into the collector image, so freshness is tied to the image rebuild cadence — bumping the pinned `grype` collector version (a newer image ships a newer DB) is what picks up new CVE data. Set `db_auto_update: true` (on a Hub that honors `size: large`) to have each re-scan fetch the latest vulnerability database instead, so CVEs published since the last scan surface on the next tick.
