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
| `.container_scan.source` | object | Source metadata for the container image scan (tool, version, integration) |
| `.container_scan.image` | string | The scanned image reference (e.g. `registry/app:tag`) |
| `.container_scan.vulnerabilities` | object | Severity counts for the image scan (critical, high, medium, low, total) |
| `.container_scan.findings[]` | array | Individual image findings (OS and application packages) |
| `.container_scan.os` | object | Detected base-image OS family and version |
| `.container_scan.summary` | object | Summary booleans (has_critical, has_high, all_fixable) |
| `.container_scan.native.grype` | object | Raw Grype match output for the image scan |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `auto` | code | Auto-scans the repository filesystem for dependency vulnerabilities → `.sca` |
| `cicd` | ci-after-command | Detects Grype executions in CI; routes image scans (`grype <image>`) to `.container_scan` and dir/SBOM scans to `.sca` |
| `rescan` | cron | Re-runs the `auto` scan on a schedule (daily by default) and overwrites `.sca` so the SCA policy re-evaluates against newly-published CVEs |
| `container-rescan` | cron | Scans the most recently shipped image (read from `.containers.builds[]`) in the Grype collector image on a schedule and writes `.container_scan` |

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

**Container image scanning.** Beyond source dependencies, this collector scans **built container images** and writes results to the normalized `.container_scan` path, consumed by the [`container-scan`](../../policies/container-scan) policy. Two sub-collectors feed it, neither of which requires the (not-yet-shipped) collector-dependency feature, and — crucially — **neither installs Grype (or its ~1.7GB vulnerability DB) in your pipeline**:

- **`cicd`** *(detect)* — if your pipeline already runs `grype <image>` itself, that scan is captured to `.container_scan` automatically. A `grype dir:`/`sbom:` scan still routes to `.sca`. No install, no extra config.
- **`container-rescan`** *(auto-scan)* — a daily cron that reads the most recently shipped image from `.containers.builds[]` (populated by the [`docker`](../docker) collector) via `lunar component get-json`, then pulls and scans it **in the Grype collector image, where the vulnerability DB is already baked in**. This is how Lunar scans the image *itself* with no install on your side, and it also re-evaluates a shipped image against CVEs published after it was built.

Because the cron reads already-persisted Component JSON (not another collector's output mid-run), it needs no collector-dependency feature. Enable the `docker` collector alongside this one so `.containers.builds[]` is populated:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/docker@main
    on: ["domain:your-domain"]
  - uses: github://earthly/lunar-lib/collectors/grype@main
    on: ["domain:your-domain"]
```

> A synchronous **on-push** auto-scan (scan the image the moment it's built, and only if CI didn't already) needs the component-JSON dependency feature — it follows once that lands.

**Private registries:** the `container-rescan` cron pulls the image, so a private registry needs the `REGISTRY_USERNAME` / `REGISTRY_PASSWORD` secrets.

> **Note:** The `grype` collector writes to the same `.sca` paths as the `snyk` and `trivy` collectors. Use one SCA scanner per component, not several, or they will overwrite each other's `.sca` data.

> **Re-scan freshness:** With the default `db_auto_update: false`, a re-scan is less likely to surface newly-published CVEs, since it uses the vulnerability DB baked into the collector image. Bumping the pinned `grype` collector version (a newer image ships a newer DB) means the next cron tick picks up the new CVE data.
