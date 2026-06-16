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
| `auto` | code | Auto-scans the repository filesystem for dependency vulnerabilities on every push |
| `cron-rescan` | cron | Re-runs the `auto` scan on a schedule and overwrites `.sca` so the SCA policy re-evaluates a branch against newly published CVEs |
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

### Scheduled re-scan (`cron-rescan`)

The `auto` collector scans on every push. The `cron-rescan` sub-collector re-runs that **same** scan (it shares `auto.sh`) on a schedule and overwrites `.sca`, so the SCA policy re-evaluates a branch against CVEs published *after* its last commit was scanned — without waiting for a new commit. This closes the gap where a stable branch passes at commit time but a dependency later picks up a new CVE.

Grype and its vulnerability database come from this collector's **own image**, so the re-scan performs **no runtime download of lunar-lib or the scanner** — it is a first-class, local re-scan, not a separate collector that fetches the scan script at runtime.

Cron runs stamp `.sca.source.integration = "cron"` and add `.sca.source.scanned_at` (an ISO-8601 timestamp), so re-scan data is distinguishable from a code-push scan.

**Scope.** `cron-rescan` defaults to **`runs_on: [default-branch]`** — the safe default that re-scans only the main branch. Re-scanning open PR heads (per-PR fan-out) is **opt-in** by widening `runs_on` on the sub-collector:

```yaml
runs_on: [prs, default-branch]
```

> **CVE-freshness caveat (grype-specific).** Grype's vulnerability database (~1.7 GB decompressed) is **pre-baked into the collector image** because downloading it at scan time OOM-kills the memory-limited collector container. The re-scan therefore finds CVEs that are only as current as the image's baked database — i.e. re-scan freshness is bounded by how often the `grype` collector image is rebuilt, not by the cron cadence. For always-current CVEs, set the `db_auto_update` input to `"true"` (fetches a fresh DB at scan time) **only on deployments that have raised per-collector memory limits**, or rebuild the `grype` image on a schedule. `trivy` does not have this constraint (its DB is much smaller and fetched at runtime).
