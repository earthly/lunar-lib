# Grype Vulnerability Scanner Collector

Scans source code dependencies for known vulnerabilities using Grype.

## Overview

This collector runs [Grype](https://github.com/anchore/grype) — Anchore's open-source vulnerability scanner — against the repository to detect known CVEs in dependencies. It supports the ecosystems Grype covers (Go, Node.js, Python, Java, Rust, Ruby, PHP, .NET, and more) and writes normalized vulnerability data to `.sca` in the Component JSON, making results immediately consumable by the existing SCA policy. No secrets or vendor accounts are required. By default it scans against the vulnerability database baked into the collector image, so freshness tracks the image rebuild cadence; set `db_auto_update: true` — on a Hub that honors the `size: large` profile these collectors declare — to fetch the latest database at scan time and pick up CVEs published since the image was built.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.sca.source` | object | Source metadata (tool name, version, integration method, and `collected_at` scan timestamp) |
| `.sca.vulnerabilities` | object | Severity counts (critical, high, medium, low, total) |
| `.sca.findings[]` | array | Individual vulnerability findings with CVE, package, fix info |
| `.sca.summary` | object | Summary booleans (has_critical, has_high, all_fixable) |
| `.sca.history[]` | array | *(opt-in)* Bounded list of prior scan snapshots (source, counts, summary) for point-in-time audit; oldest first. `[0]` is the oldest retained scan — the release-time (`integration="code"`) scan when history is enabled from the first scan. Absent unless `scan_history_size > 0` |
| `.sca.rescan_count` | number | *(opt-in)* Monotonic tally of completed re-scans, used to enforce `max_rescans` independently of the (capped) `.sca.history[]` length. Present when scan history or `max_rescans` is enabled |
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
| `rescan` | cron | Re-runs the `auto` scan on a schedule (daily by default) and overwrites `.sca` so the SCA policy re-evaluates against newly-published CVEs; optionally snapshots prior scans into `.sca.history[]` (opt-in via `scan_history_size` — see [Scan history](#scan-history-point-in-time-audit)) |
| `container-scan` | after-json | Automatically scans the image the docker collector records as **pushed** (`.containers.native.docker.cicd.cmds[]`) as soon as it's published; writes `.container_scan` |
| `container-rescan` | cron | Re-scans the most recently **pushed** image on a schedule, catching CVEs disclosed since it was built |

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

### Scan history (point-in-time audit)

By default the `rescan` cron **overwrites** `.sca` each run — the SCA policy
always sees the latest scan and the previous result is discarded. Because an
**unchanged** artifact accrues newly-disclosed CVEs over time, you may want to
keep each scan as a point-in-time record (e.g. "here's what the scan looked
like when we shipped this release"). Opt in by keeping a bounded history:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/grype@main
    on: ["domain:your-domain"]
    with:
      scan_history_size: "30"   # keep up to 30 prior scans in .sca.history[]
      max_rescans: "0"          # 0 = keep re-scanning forever (default)
```

With `scan_history_size > 0`, each re-scan snapshots the current `.sca`
(source + counts + summary, including the `collected_at` timestamp) into
`.sca.history[]` **before** overwriting `.sca`:

- `.sca` (unchanged) — the **current** scan the SCA policy evaluates.
- `.sca.history[0]` — the **oldest retained** scan, preserved even once the cap
  is reached. When history is enabled from the component's first scan (the
  intended setup) this is the **release-time** scan; each entry carries its own
  `source` (`integration` + `collected_at`), so the release-time scan is the
  `integration: "code"` entry — not an assumption about position.
- `.sca.history[1..]` — successive prior re-scans, oldest first.

> **Enabling history on an already-scanned component:** if a component has
> already been re-scanning (overwriting `.sca`) before you turn on
> `scan_history_size`, its release-time scan is already gone, so `.sca.history[0]`
> will be the current `.sca` at enable time (an `integration: "cron"` entry), not
> the original `code` scan. For guaranteed release-time capture, enable history
> from the component's first scan.

The SCA policy never reads `.sca.history`, so enabling this changes nothing for
policy evaluation — `.sca` behaves identically whether history is on or off.

| Input | Default | Effect |
|-------|---------|--------|
| `scan_history_size` | `0` | Max entries kept in `.sca.history[]`. `0` disables history (today's overwrite-only behavior). At the cap the oldest entry (`[0]`) is kept and the second-oldest is dropped. |
| `max_rescans` | `0` | Stop re-scanning a component after this many re-scans (`0` = unlimited). Counted independently via `.sca.rescan_count`, so it stands alone — no dependency on `scan_history_size`. |

Both default to off, so existing installs are unchanged. Only the `rescan` cron
maintains history — the on-push `auto` scan ignores these inputs.

**Container image scanning.** Beyond source dependencies, this collector scans **built container images** into the normalized `.container_scan` path (consumed by the [`container-scan`](../../policies/container-scan) policy). Three sub-collectors feed it, **none installing Grype (or its ~1.7GB DB) in your pipeline**:

- **`cicd`** *(detect)* — if your pipeline already runs `grype <image>` itself, that scan is captured to `.container_scan` automatically. A `grype dir:`/`sbom:` scan still routes to `.sca`. No install, no extra config.
- **`container-scan`** *(on-push)* — automatically scans the image as soon as it's published. Hooks `after-json` on `.containers.native.docker.cicd.cmds`, so a scan fires the moment the docker collector records a push — no schedule lag.
- **`container-rescan`** *(scheduled re-scan)* — a daily cron that re-scans that image, catching CVEs **disclosed after it was built**.

All three scan the shipped image *itself* in the Grype collector image (DB baked in) — no install on your side. Enable the [`docker`](../docker) collector alongside this one so its `docker push` commands are recorded:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/docker@main
    on: ["domain:your-domain"]
  - uses: github://earthly/lunar-lib/collectors/grype@main
    on: ["domain:your-domain"]
```

> **`container-scan` needs a Hub with the `after-json` hook.** Without it, `exclude: [container-scan]` and rely on the `container-rescan` cron (the other sub-collectors work on any Hub).

**Private registries:** the `container-rescan` cron pulls the image, so a private registry needs the `REGISTRY_USERNAME` (or `REGISTRY_USER`) / `REGISTRY_PASSWORD` secrets.

> **Note:** The `grype` collector writes to the same `.sca` paths as the `snyk` and `trivy` collectors. Use one SCA scanner per component, not several, or they will overwrite each other's `.sca` data.

> **Re-scan freshness:** By default (`db_auto_update: false`), each cron re-scan uses the DB baked into the collector image, so freshness is tied to the image rebuild cadence — bumping the pinned `grype` collector version (a newer image ships a newer DB) is what picks up new CVE data. Set `db_auto_update: true` (on a Hub that honors `size: large`) to have each re-scan fetch the latest vulnerability database instead, so CVEs published since the last scan surface on the next tick.
