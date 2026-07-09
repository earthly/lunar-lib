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
| `container-rescan` | cron | Scans the most recently **pushed** image (resolved from the docker collector's recorded `docker push` / `--push` commands) in the Trivy collector image on a schedule and writes `.container_scan` |

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

**Container image scanning.** Beyond source dependencies, this collector scans **built container images** and writes results to the normalized `.container_scan` path, consumed by the [`container-scan`](../../policies/container-scan) policy. Two sub-collectors feed it, neither of which requires the (not-yet-shipped) collector-dependency feature, and neither of which installs Trivy in your pipeline:

- **`cicd`** *(detect)* — if your pipeline already runs `trivy image <ref>` itself, that scan is captured to `.container_scan` automatically. A `trivy fs` scan still routes to `.sca`. No install, no extra config.
- **`container-rescan`** *(auto-scan)* — a daily cron that resolves the most recently **pushed** image from the [`docker`](../docker) collector's recorded commands (`.containers.native.docker.cicd.cmds[]` — the latest `docker push`, or a `--push` build) via `lunar component get-json`, then pulls and scans it **in the Trivy collector image**. Resolving from *pushes* rather than `.containers.builds[]` means a built-but-never-pushed (test/dry-run) image isn't scanned. This is how Lunar scans the shipped image *itself* — without installing Trivy in your CI — and it re-evaluates that image against CVEs published after it was built. (No push recorded → nothing to scan; the cron skips. Use the `container_image` input to pin an image explicitly.)

Because the cron reads already-persisted Component JSON (not another collector's output mid-run), it needs no collector-dependency feature. Enable the `docker` collector alongside this one so its CI `docker push` commands are recorded:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/docker@main
    on: ["domain:your-domain"]
  - uses: github://earthly/lunar-lib/collectors/trivy@main
    on: ["domain:your-domain"]
```

> A synchronous **on-push** auto-scan (scan the image the moment it's built, and only if CI didn't already) needs the component-JSON dependency feature — it follows once that lands.

**Private registries:** the `container-rescan` cron pulls the image, so a private registry needs the `REGISTRY_USERNAME` (or `REGISTRY_USER`) / `REGISTRY_PASSWORD` secrets. Trivy's vulnerability database is a modest download at scan time.

> **Note:** If you already use the `snyk` collector, the `trivy` collector will overwrite `.sca` data since both write to the same paths. Use one SCA scanner per component, not both.
