# Trivy Vulnerability Scanner Collector

Scans source code dependencies for known vulnerabilities using Trivy.

## Overview

This collector runs Trivy filesystem scans against repository source code to detect known CVEs in dependencies. It supports all ecosystems Trivy covers (Go, Node.js, Python, Java, Rust, Ruby, PHP, .NET, etc.) and writes normalized vulnerability data to `.sca` in the Component JSON, making results immediately consumable by the existing SCA policy. A scheduled `rescan` re-runs the same scan on a cron and overwrites `.sca`, so a previously-clean commit is re-evaluated against CVEs published after it was first scanned.

No secrets or vendor accounts are required — Trivy's vulnerability database is downloaded at scan time to ensure the latest CVE data.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.sca.source` | object | Source metadata (tool name, version, integration method) |
| `.sca.vulnerabilities` | object | Severity counts (critical, high, medium, low, total) |
| `.sca.findings[]` | array | Individual vulnerability findings with CVE, package, fix info |
| `.sca.summary` | object | Summary booleans (has_critical, has_high, all_fixable) |
| `.sca.native.trivy.cicd` | object | CI command detection data (command, version) |
| `.container_scan.source` | object | Source metadata for the container image scan (tool, version, integration) |
| `.container_scan.image` | string | The scanned image reference (e.g. `registry/app:tag`) |
| `.container_scan.vulnerabilities` | object | Severity counts for the image scan (critical, high, medium, low, total) |
| `.container_scan.findings[]` | array | Individual image findings (OS and application packages) |
| `.container_scan.os` | object | Detected base-image OS family and version |
| `.container_scan.summary` | object | Summary booleans (has_critical, has_high, all_fixable) |
| `.container_scan.native.trivy` | object | Raw Trivy results for the image scan |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `auto` | code | Auto-scans the repository filesystem for dependency vulnerabilities → `.sca` |
| `cicd` | ci-after-command | Detects Trivy executions in CI; routes image scans (`trivy image <ref>`) to `.container_scan` and filesystem scans (`trivy fs`) to `.sca` |
| `rescan` | cron | Re-runs the `auto` scan on a schedule (daily by default) and overwrites `.sca` so the SCA policy re-evaluates against newly-published CVEs |
| `container-ci` | ci-after-command | Scans the image shipped by `docker push` in CI and writes `.container_scan` |
| `container-rescan` | cron | Re-scans the most recently pushed image (read from `.containers.builds[]`) on a schedule and overwrites `.container_scan` |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/trivy@main
    on: ["domain:your-domain"]
```

Zero configuration required. Works with any language Trivy supports.

By default this also enables the `rescan` cron sub-collector, which re-runs the
scan daily on each component's default branch and overwrites `.sca`. To keep the
on-push (`auto`) and CI-detection (`cicd`) scans but turn the scheduled re-scan
off, exclude it:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/trivy@main
    on: ["domain:your-domain"]
    exclude: [rescan]
```

**Container image scanning.** Beyond source dependencies, this collector scans **built container images** and writes results to the normalized `.container_scan` path, consumed by the [`container-scan`](../../policies/container-scan) policy. Three sub-collectors feed it, none of which require the (not-yet-shipped) collector-dependency feature:

- **`container-ci`** — fires on `docker push` in CI, scans the just-shipped image (already present in the CI Docker daemon; the reference comes straight from the push command), and writes `.container_scan`.
- **`cicd`** — if your pipeline already runs `trivy image <ref>` itself, that scan is captured to `.container_scan` automatically. A `trivy fs` scan still routes to `.sca`.
- **`container-rescan`** — a nightly cron that reads the most recently pushed image from `.containers.builds[]` (populated by the [`docker`](../docker) collector) via `lunar component get-json`, pulls it, and re-scans — surfacing CVEs published after the image shipped.

Because the cron reads already-persisted Component JSON (not another collector's output mid-run), it needs no collector-dependency feature. Enable the `docker` collector alongside this one so `.containers.builds[]` is populated:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/docker@main
    on: ["domain:your-domain"]
  - uses: github://earthly/lunar-lib/collectors/trivy@main
    on: ["domain:your-domain"]
```

**Private registries:** the `container-rescan` cron pulls the image, so a private registry needs the `REGISTRY_USERNAME` / `REGISTRY_PASSWORD` secrets. The `container-ci` scan runs inside your CI where the image is already local, so it usually needs no extra credentials. Both modes download Trivy's vulnerability database at scan time (a modest download — lighter than image-baked scanners).

> **Note:** If you already use the `snyk` collector, the `trivy` collector will overwrite `.sca` data since both write to the same paths. Use one SCA scanner per component, not both.
